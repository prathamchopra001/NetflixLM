"""Ray Serve applications per deployed variant: deploy, teardown, staged/resident execution.

docs/hardware-adaptation.md › Execution. One application per variant, `nip-<variant>` at
`/models/<variant>`; a shared variant (text_llm + vlm, a reusing judge) is one application.
LLM/VLM replicas start the image's `vllm serve` as a child process on the GPU(s) Ray assigned
and forward HTTP to it. Actor slots get their real backends with their own deliverables
(Phase 2+); until then they deploy a placeholder that holds the Plan's GPU fraction.
Stub variants (NIP_PROFILE=cpu) deploy nothing: their clients answer in-process.

Ray is imported lazily, so the Windows / cpu profile imports this module without it.
`serve` parameters take the `ray.serve` module (or a fake with the same calls in tests).
"""

import importlib
import json
import os
import signal
import socket
import subprocess
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nip.contracts import HardwareInventory, Plan, Slot, SlotDecision, StageGroup
from nip.runtime.catalog import Catalog, Variant

ENFORCE_EAGER_MAX_GB = 16.0  # CUDA graphs cost ~0.5-1 GiB: skip them on GPUs this small
STARTUP_TIMEOUT_S = 900.0
IDLE_TOLERANCE_MIB = 256  # desktop apps move free VRAM by ~100 MiB on the laptop
MAX_ONGOING_REQUESTS = 64  # per vLLM replica; the scheduler bounds units in flight anyway


class ServingError(RuntimeError):
    pass


@dataclass(frozen=True)
class App:
    """One Serve application: a variant, the Plan slots it serves, its replicas and GPUs."""

    variant: str
    slots: tuple[Slot, ...]
    replicas: int
    num_gpus: float
    vllm_args: tuple[str, ...] = ()  # empty: actor placeholder

    @property
    def name(self) -> str:
        return f"nip-{self.variant}"

    @property
    def route_prefix(self) -> str:
        return f"/models/{self.variant}"


STRUCTURED_OUTPUTS = {"backend": "xgrammar", "disable_any_whitespace": True}


def vllm_args(v: Variant, d: SlotDecision, vlm: SlotDecision | None, *, eager: bool) -> list[str]:
    """`vllm serve` arguments from the Plan decision (hardware-adaptation.md › Serving).

    With an exact KV budget (`kv_cache_bytes`), gpu_memory_utilization only gates vLLM's startup
    check. `--kv-cache-dtype fp8` is left to EXP-018 (KV-cache precision on the laptop)."""
    if not (v.repo and d.context and d.gpu_memory_utilization):
        raise ServingError(f"{v.id}: the Plan decision lacks a repo, context or gmu: {d}")
    args = [
        v.repo,
        "--served-model-name", v.id,
        "--tensor-parallel-size", str(d.gpus_per_replica or 1),
        "--max-model-len", str(d.context),
        "--gpu-memory-utilization", str(d.gpu_memory_utilization),
    ]  # fmt: skip
    if d.kv_cache_bytes is not None:
        args += ["--kv-cache-memory-bytes", str(d.kv_cache_bytes)]
    # Compact guided JSON (2.1 proposal 6): with whitespace allowed between fields, ~5% of
    # extraction scenes stopped mid-object and emitted spaces until max_tokens. xgrammar is one of
    # the two backends that support it (vLLM 0.30 rejects it under "auto").
    args += ["--structured-outputs-config", json.dumps(STRUCTURED_OUTPUTS)]
    if eager:
        args.append("--enforce-eager")
    if vlm and vlm.images_per_prompt is not None:
        args += ["--limit-mm-per-prompt.image", str(vlm.images_per_prompt)]
    if vlm and vlm.max_pixels is not None:
        args += ["--mm-processor-kwargs", json.dumps({"max_pixels": vlm.max_pixels})]
    return args


def apps(
    plan: Plan, catalog: Catalog, inventory: HardwareInventory, slots: list[Slot]
) -> list[App]:
    """Applications for these Plan slots (a stage group): one per non-stub variant."""
    variants = {v.id: v for v in catalog.variants}
    eager = (
        min((g.vram_total_gb for n in inventory.nodes for g in n.gpus), default=0.0)
        <= ENFORCE_EAGER_MAX_GB
    )
    out: list[App] = []
    for vid in dict.fromkeys(plan.decisions[s].variant for s in slots):
        v = variants[vid]
        if v.engine == "stub":
            continue
        # The primary decision carries replicas/GPUs; secondary (shared) ones only the variant.
        main = next(d for d in plan.decisions.values() if d.variant == vid and d.replicas)
        served = tuple(s for s in slots if plan.decisions[s].variant == vid)
        num_gpus = main.gpu_fraction if main.gpu_fraction is not None else main.gpus_per_replica
        args: tuple[str, ...] = ()
        if v.engine == "vllm":
            vlm = plan.decisions.get(Slot.VLM)
            vlm = vlm if vlm and vlm.variant == vid else None
            args = tuple(vllm_args(v, main, vlm, eager=eager))
        out.append(App(vid, served, main.replicas or 1, float(num_gpus or 0), args))
    return out


# ---- Serve deployments (run inside Ray replicas) ---------------------------------------------
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _group_running(pgid: int) -> bool:
    """A non-zombie process in the group. Zombies don't count: the container's PID 1 (`ray`)
    never reaps the orphaned EngineCore, and a zombie holds no GPU memory."""
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = stat.read_text().rsplit(")", 1)[1].split()  # state, ppid, pgrp, ...
        except OSError:
            continue
        if fields[0] != "Z" and int(fields[2]) == pgid:
            return True
    return False


class VllmServer:
    """Serve replica: `vllm serve` on this replica's GPUs, requests forwarded over localhost."""

    def __init__(
        self, variant: str, args: list[str], prefix: str, timeout_s: float = STARTUP_TIMEOUT_S
    ) -> None:
        self.prefix = prefix
        port = _free_port()
        log_dir = Path(os.environ.get("NIP_VLLM_LOG_DIR", "/tmp/nip-vllm"))
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log = log_dir / f"{variant}-{os.getpid()}.log"
        cmd = ["vllm", "serve", *args, "--host", "127.0.0.1", "--port", str(port)]
        with self.log.open("wb") as f:
            # Own process group, so teardown kills vLLM's engine-core children too.
            # ponytail: a replica killed with SIGKILL (no __del__) orphans vLLM; teardown's VRAM
            # check catches it. Add a PDEATHSIG wrapper if that ever happens in practice.
            self.proc = subprocess.Popen(
                cmd, stdout=f, stderr=subprocess.STDOUT, start_new_session=True
            )
        self.base = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + timeout_s
        while not self._healthy():
            if self.proc.poll() is not None or time.monotonic() > deadline:
                why = "exited" if self.proc.poll() is not None else f"not healthy in {timeout_s}s"
                self.stop()
                tail = self.log.read_text(errors="replace")[-3000:]
                raise ServingError(f"vllm serve {variant} {why} (log {self.log}):\n{tail}")
            time.sleep(1)

    def _healthy(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base}/health", timeout=2) as r:
                return bool(r.status == 200)
        except OSError:
            return False

    def stop(self, timeout_s: float = 30.0) -> None:
        """SIGTERM the whole process group, SIGKILL whatever still runs after `timeout_s`. Done even
        when `vllm serve` itself has exited: its EngineCore child can outlive it and hold VRAM."""
        pgid = self.proc.pid  # start_new_session: the group id is the leader's pid
        deadline = time.monotonic() + timeout_s
        try:
            os.kill(-pgid, signal.SIGTERM)
            while _group_running(pgid):
                self.proc.poll()  # reap the leader
                if time.monotonic() >= deadline:
                    os.kill(-pgid, 9)  # SIGKILL (the name is absent on Windows)
                    break
                time.sleep(0.2)
        except ProcessLookupError:
            pass
        self.proc.poll()

    def __del__(self) -> None:  # Serve calls this on graceful replica shutdown
        if hasattr(self, "proc"):
            self.stop()

    def check_health(self) -> None:
        if self.proc.poll() is not None:
            raise ServingError(f"vllm serve exited with {self.proc.returncode}")

    async def __call__(self, request: Any) -> Any:
        import httpx  # vLLM's dependency; present in the nip image
        from starlette.responses import Response

        path = request.url.path.removeprefix(self.prefix)
        # ponytail: buffers the whole response (no streaming); add when a caller streams.
        async with httpx.AsyncClient(timeout=None) as c:
            r = await c.request(
                request.method,
                self.base + path,
                params=request.query_params,
                content=await request.body(),
                headers={"content-type": request.headers.get("content-type", "application/json")},
            )
        return Response(r.content, r.status_code, media_type=r.headers.get("content-type"))


class Placeholder:
    """Actor slot without a real backend yet: holds its GPU fraction, answers as a stub."""

    def __init__(self, variant: str) -> None:
        self.variant = variant

    async def __call__(self, request: Any) -> dict[str, Any]:
        return {"variant": self.variant, "stub": True}


# ---- Lifecycle (run by the controller, connected to Ray) -------------------------------------
def ray_serve() -> Any:
    """`ray.serve`, connected to the cluster at NIP_RAY_ADDRESS, HTTP on every node's :8000."""
    import ray
    from ray import serve

    if not ray.is_initialized():
        ray.init(address=os.environ.get("NIP_RAY_ADDRESS", "auto"), log_to_driver=False)
    serve.start(http_options={"host": "0.0.0.0", "port": 8000})
    return serve


def actor_class(slot: Slot) -> type:
    """`nip.runtime.clients.<slot>.Actor` when that module defines one, else `Placeholder`."""
    try:
        mod = importlib.import_module(f"nip.runtime.clients.{slot}")
    except ModuleNotFoundError as e:
        if e.name != f"nip.runtime.clients.{slot}":
            raise  # the client module exists but one of its imports is missing
        return Placeholder
    cls: type = getattr(mod, "Actor", Placeholder)
    return cls


def _bind(a: App, serve: Any) -> Any:
    if a.vllm_args:
        cls: type = VllmServer
        init: tuple[Any, ...] = (a.variant, list(a.vllm_args), a.route_prefix)
    else:
        actors = {actor_class(s) for s in a.slots}
        if len(actors) > 1:  # one variant serving slots with different actors: a catalog bug
            raise ServingError(f"{a.variant}: slots {a.slots} bind different actors {actors}")
        cls, init = actors.pop(), (a.variant,)
    return (
        serve.deployment(cls)
        .options(
            name=a.variant,
            num_replicas=a.replicas,
            ray_actor_options={"num_gpus": a.num_gpus},
            max_ongoing_requests=MAX_ONGOING_REQUESTS,
            # One attempt: a vLLM start that fails for memory fails again; the scheduler
            # retries smaller or downgrades (hardware-adaptation.md › Elasticity).
            max_constructor_retry_count=1,
            graceful_shutdown_timeout_s=60,
        )
        .bind(*init)
    )


def _why(serve: Any, name: str) -> str:
    """The replica's constructor error from Serve's status (serve.run's own error omits it)."""
    try:
        app = serve.status().applications[name]
        return "\n".join([app.message, *(d.message for d in app.deployments.values())])
    except Exception:  # status unavailable: the run error alone has to do
        return ""


def deploy(apps_: list[App], serve: Any) -> dict[str, float]:
    """Start each app; on an existing name Serve updates it in place (new replica count = scale).
    Blocks until every app is RUNNING; returns load seconds per app."""
    secs: dict[str, float] = {}
    for a in apps_:
        t = time.monotonic()
        try:
            serve.run(_bind(a, serve), name=a.name, route_prefix=a.route_prefix)
        except Exception as e:
            raise ServingError(f"{a.name} failed to deploy: {e}\n{_why(serve, a.name)}") from e
        secs[a.name] = round(time.monotonic() - t, 1)
    return secs


def gpu_used_mib() -> int:
    """Used VRAM on this node's GPUs (NVML; on WSL2 this includes the Windows desktop's share)."""
    import pynvml

    pynvml.nvmlInit()
    try:
        n = pynvml.nvmlDeviceGetCount()
        handles = [pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(n)]
        return sum(int(pynvml.nvmlDeviceGetMemoryInfo(h).used) for h in handles) // 2**20
    finally:
        pynvml.nvmlShutdown()


def teardown(
    apps_: list[App],
    serve: Any,
    idle_mib: int | None = None,
    used_mib: Callable[[], int] = gpu_used_mib,
    timeout_s: float = 120.0,
) -> float:
    """Delete the apps; with `idle_mib`, wait until used VRAM is back within tolerance of it.
    Returns seconds until idle. ponytail: checks this node's GPUs only; a multi-node check
    runs the probe per node as Ray tasks (controller)."""
    t = time.monotonic()
    for a in apps_:
        serve.delete(a.name)
    if idle_mib is None:
        return round(time.monotonic() - t, 1)
    while (used := used_mib()) > idle_mib + IDLE_TOLERANCE_MIB:
        if time.monotonic() - t > timeout_s:
            raise ServingError(f"VRAM used {used} MiB after teardown, idle was {idle_mib} MiB")
        time.sleep(0.5)
    return round(time.monotonic() - t, 1)


def run(
    plan: Plan,
    catalog: Catalog,
    inventory: HardwareInventory,
    work: Callable[[StageGroup], None],
    serve: Any,
    used_mib: Callable[[], int] = gpu_used_mib,
) -> list[dict[str, Any]]:
    """Execute the Plan's groups in order: deploy -> work(group) -> teardown -> VRAM back to idle.
    Staged mode has one group per load; a resident Plan has one group `resident`, so the same loop
    keeps everything up for the whole run. Returns load/unload seconds per group."""
    out: list[dict[str, Any]] = []
    for g in plan.groups:
        group = apps(plan, catalog, inventory, g.slots)
        idle = used_mib()
        try:
            loads = deploy(group, serve)
            work(g)
        except BaseException as e:  # tear down, but keep the original error as the cause
            try:
                teardown(group, serve, idle, used_mib)
            except ServingError as t:
                e.add_note(f"teardown after this failure also failed: {t}")
            raise
        unload_s = teardown(group, serve, idle, used_mib)
        out.append({"group": g.name, "load_s": loads, "unload_s": unload_s})
    return out
