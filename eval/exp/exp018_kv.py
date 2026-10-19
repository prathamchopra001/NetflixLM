"""EXP-018: KV-cache precision on the laptop (default KV at 8k · FP8 KV at 8k · FP8 KV at 16k), plus
the GPU plumbing of 2.1B's extraction passes (one deployment per arm, `up` / `down`).

Each arm is the shipped plan (probe -> planner, NIP_VRAM_MARGIN_GB) with two overrides: the context
(`--max-model-len`) and, for fp8 arms, `--kv-cache-dtype fp8`. The KV budget stays the planner's
exact `--kv-cache-memory-bytes` (the GPU's leftover), so an fp8 arm holds twice the tokens in the
same bytes. Extra arms: `default-16k` (what the planner picks today) and `fp8-32k` (the doubling of
that). Start trials as EXP-001: deploy -> 8 x 128-token bench -> teardown, VRAM back to idle.

    # ray-head from a clean shell (no host NIP_DATABASE_URL), weights offline:
    HF_HUB_OFFLINE=1 docker compose -f compose.yaml -f compose.dev.yaml up -d --wait ray-head
    uv run python -m eval.exp.exp018_kv drive --arms default-8k,fp8-8k,fp8-16k --trials 10
        (rounds of one trial per arm in ray-head; data/gpu.lock held per round)
    uv run python -m eval.exp.exp018_kv log          # data/exp018/trials.jsonl -> MLflow
    uv run nip eval compare --exp EXP-018 --md --tracking-uri sqlite:///data/mlflow/mlflow.db
  ray-head (inside `exec`):  python3 -m eval.exp.exp018_kv up --arm fp8-8k   |   down
Fact precision/recall per arm: eval.exp.exp020_rules (`extract` against an arm's deployment).
"""

import json
import os
import shutil
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any

import typer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "exp018"
LOCK = ROOT / "data" / "gpu.lock"
TRACKING_URI = f"sqlite:///{(ROOT / 'data' / 'mlflow' / 'mlflow.db').as_posix()}"
VARIANT = "qwen3.5-4b-awq"
ARMS = {  # arm -> (max_model_len, fp8 KV)
    "default-8k": (8192, False),
    "fp8-8k": (8192, True),
    "fp8-16k": (16384, True),
    "default-16k": (16384, False),
    "fp8-32k": (32768, True),
}
COMPOSE = ["docker", "compose", "-f", "compose.yaml", "-f", "compose.dev.yaml"]
STATE = Path("/tmp/exp018-app.json")  # inside ray-head: the deployed app, for `down`
app = typer.Typer(no_args_is_help=True)


# ---- ray-head ----------------------------------------------------------------------------------
def arm_app(arm: str) -> tuple[Any, dict[str, Any]]:
    """The shipped plan's text_llm app with the arm's context and KV dtype."""
    from nip.config import vram_margin_gb
    from nip.contracts import Slot
    from nip.runtime.catalog import load_catalog
    from nip.runtime.planner import plan
    from nip.runtime.probe import probe
    from nip.runtime.serving import App, vllm_args

    ctx, fp8 = ARMS[arm]
    cat, inv = load_catalog(), probe()
    p = plan(inv, cat, {Slot.TEXT_LLM: 1}, margin_gb=vram_margin_gb())
    if Slot.TEXT_LLM in p.skipped_slots:
        raise typer.BadParameter(f"planner skipped text_llm: {p.warnings}")
    v = next(v for v in cat.variants if v.id == VARIANT)
    d = p.decisions[Slot.TEXT_LLM].model_copy(update={"context": ctx})
    args = vllm_args(v, d, None, eager=True) + (["--kv-cache-dtype", "fp8"] if fp8 else [])
    a = App(VARIANT, (Slot.TEXT_LLM,), 1, float(d.gpu_fraction or 1), tuple(args))
    info = {
        "planned_context": p.decisions[Slot.TEXT_LLM].context,
        "free_gb": inv.nodes[0].gpus[0].vram_free_gb,
    }
    return a, d.model_dump(exclude_none=True) | info


def _vllm_log(before: set[Path]) -> str:
    d = Path(os.environ.get("NIP_VLLM_LOG_DIR", "/tmp/nip-vllm"))
    new = sorted(set(d.glob("*.log")) - before, key=lambda p: p.stat().st_mtime)
    return new[-1].read_text(errors="replace") if new else ""


def _logs() -> set[Path]:
    d = Path(os.environ.get("NIP_VLLM_LOG_DIR", "/tmp/nip-vllm"))
    return set(d.glob("*.log")) if d.exists() else set()


@app.command()
def up(arm: Annotated[str, typer.Option()]) -> None:
    """Deploy the arm's app (for an extraction pass); `down` removes it."""
    from dataclasses import asdict

    from eval.exp.exp001_vllm_headroom import parse_log
    from nip.runtime.serving import deploy, gpu_used_mib, ray_serve

    a, d = arm_app(arm)
    idle, before = gpu_used_mib(), _logs()
    secs = deploy([a], ray_serve())[a.name]
    STATE.write_text(json.dumps({"app": asdict(a), "idle": idle}))
    out = {"arm": arm, "load_s": secs, "idle_mib": idle, "up_mib": gpu_used_mib(), "decision": d}
    typer.echo(json.dumps(out | parse_log(_vllm_log(before)) | {"args": a.vllm_args}))


@app.command()
def down() -> None:
    """Delete every Serve app (by status, not by re-planning: with the model loaded the planner no
    longer fits it, 2.2B's finding) and wait until VRAM is back within 1 GiB of `up`'s idle."""
    from nip.runtime.serving import ray_serve, teardown

    s = json.loads(STATE.read_text()) if STATE.exists() else {"idle": None}
    serve = ray_serve()
    t = time.monotonic()
    for name in list(serve.status().applications):
        serve.delete(name)
    secs = teardown([], serve, idle_mib=s["idle"], tolerance_mib=1024)
    STATE.unlink(missing_ok=True)
    typer.echo(
        json.dumps(
            {"unload_s": round(time.monotonic() - t, 1), "wait_s": secs, "idle_mib": s["idle"]}
        )
    )


@app.command()
def trial(arm: Annotated[str, typer.Option()], trial: Annotated[int, typer.Option()]) -> None:
    """One start -> bench -> teardown; prints one JSON line (the host logs it)."""
    from eval.exp.exp001_vllm_headroom import _bench, _Vram, classify, parse_log
    from nip.runtime.serving import ServingError, deploy, ray_serve, teardown

    vram = _Vram()
    used0, free0 = vram.read()
    m: dict[str, Any] = {
        "arm": arm,
        "trial": trial,
        "free_mib_start": free0,
        "used_mib_start": used0,
    }
    a, d = arm_app(arm)
    m |= {"kv_cache_bytes": d.get("kv_cache_bytes"), "max_model_len": d["context"]}
    serve, before = ray_serve(), _logs()
    vram.start()
    try:
        m["load_s"], m["started"] = deploy([a], serve)[a.name], 1
    except ServingError as e:
        m["started"], m["error"] = 0, str(e)[-2000:]
    if m["started"]:
        try:
            m["tokens_per_s"] = round(_bench("http://127.0.0.1:8000"), 1)
        except Exception as e:  # a failed bench must not skip teardown
            m["bench_error"] = repr(e)[-500:]
    try:
        m["unload_s"], m["returned_to_idle"] = teardown([a], serve, idle_mib=used0), 1
    except ServingError as e:
        m["returned_to_idle"], m["teardown_error"] = 0, str(e)
    m["peak_used_mib"] = vram.stop()
    m["peak_mib"] = m["peak_used_mib"] - used0
    m["vram_after_mib"] = vram.read()[0]
    text = _vllm_log(before)
    m |= parse_log(text)
    if not m["started"]:
        m["failure"] = classify(text + m.get("error", ""))
    typer.echo("RESULT " + json.dumps(m))


# ---- host --------------------------------------------------------------------------------------
def acquire(purpose: str, poll_s: int = 60) -> None:
    """data/gpu.lock (phase2-plan.md › GPU contention): atomic mkdir + owner.txt; polls."""
    while True:
        try:
            LOCK.mkdir()
            break
        except FileExistsError:
            typer.echo(f"gpu.lock held: {owner()[:200]!r}")
            time.sleep(poll_s)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    (LOCK / "owner.txt").write_text(f"2.1B {purpose} {stamp} {TOKEN}\n")


TOKEN = f"pid {os.getpid()}"  # ends owner.txt: which process holds the lock (re-review N1)


def owner() -> str:
    try:
        return (LOCK / "owner.txt").read_text(errors="replace")
    except OSError:  # no lock, or another holder between its mkdir and its owner.txt
        return ""


def holds_lock() -> bool:
    """Does this process hold data/gpu.lock (its token at the end of owner.txt)?"""
    return owner().rstrip().endswith(TOKEN)


def release() -> None:
    """Remove the lock only if this process holds it, never another agent's (re-review N1)."""
    if holds_lock():
        shutil.rmtree(LOCK, ignore_errors=True)


def ray_head(*args: str, env: dict[str, str] | None = None) -> str:
    """Run `python3 -m eval.exp.exp018_kv <args>` (or any argv) inside ray-head; stdout."""
    e = [x for k, v in (env or {}).items() for x in ("-e", f"{k}={v}")]
    cmd = [*COMPOSE, "exec", "-T", *e, "ray-head", *args]
    # vLLM logs UTF-8; the Windows default (cp1252) crashed the decode and the round's teardown
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, check=False, text=True,
                       encoding="utf-8", errors="replace")  # fmt: skip
    if r.returncode:
        typer.echo(r.stderr[-3000:], err=True)
    return r.stdout


BUSY_MIB = 1500  # device use before a round; above it the planner no longer places the model


def host_used_mib() -> int:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, check=True).stdout  # fmt: skip
    return int(out.split()[0])


@contextmanager
def gpu_session(purpose: str, arm: str | None = None) -> Iterator[None]:
    """Hold data/gpu.lock for one GPU job: wait while the desktop holds the room (lock released
    meanwhile), deploy `arm` if given, run the body, then delete every Serve app and release. Every
    step after `acquire` is inside the `try`: a crash once left the lock held for 2 h 15 min."""
    acquire(purpose)
    try:
        while (used := host_used_mib()) > BUSY_MIB:  # not a fair start: wait, lock released
            typer.echo(f"desktop holds {used} MiB > {BUSY_MIB}; lock released, retry in 5 min")
            release()
            time.sleep(300)
            acquire(purpose)
        if arm:
            out = ray_head("python3", "-m", "eval.exp.exp018_kv", "up", "--arm", arm, env=MARGIN)
            if '"load_s"' not in out:
                raise typer.BadParameter(f"{arm} did not deploy: {out[-1500:]}")
            typer.echo(out[-1500:])
        yield
    finally:
        if holds_lock():  # interrupted while waiting: another holder's apps and lock stay (N1)
            try:  # safety net: no Serve app may outlive the session (2.2B's `down` finding)
                typer.echo(ray_head("python3", "-m", "eval.exp.exp018_kv", "down")[-300:])
                if (used := host_used_mib()) > BUSY_MIB:  # released anyway; say so (review M2)
                    typer.echo(f"lock released with {used} MiB used on the device", err=True)
            finally:
                release()


MARGIN = {"NIP_VRAM_MARGIN_GB": os.environ.get("NIP_VRAM_MARGIN_GB", "0.25")}


@app.command()
def drive(
    arms: Annotated[str, typer.Option(help="comma-separated")] = "default-8k,fp8-8k,fp8-16k",
    trials: int = 10,
    start: int = 1,
) -> None:
    """Rounds of one trial per arm (interleaved, so desktop VRAM drift hits every arm alike); the
    lock is taken per round and released between rounds."""
    OUT.mkdir(parents=True, exist_ok=True)
    for t in range(start, trials + 1):
        with gpu_session(f"EXP-018 start trials round {t}"):
            for arm in arms.split(","):
                typer.echo(f"== {arm} trial {t} {time.strftime('%H:%M:%S')}")
                out = ray_head("python3", "-m", "eval.exp.exp018_kv", "trial", "--arm", arm,
                               "--trial", str(t), env=MARGIN)  # fmt: skip
                line = next((x for x in out.splitlines() if x.startswith("RESULT ")), None)
                if line is None:
                    typer.echo(f"no result: {out[-2000:]}", err=True)
                    continue
                with (OUT / "trials.jsonl").open("a", encoding="utf-8") as f:
                    f.write(line.removeprefix("RESULT ") + "\n")
                typer.echo(line[:400])
        if t < trials:
            time.sleep(150)  # longer than the others' 60 s lock poll, so they get a turn


@app.command()
def log() -> None:
    """One MLflow run per trial (exp EXP-018, variant = arm, seed = trial)."""
    import mlflow

    rows = [json.loads(x) for x in (OUT / "trials.jsonl").read_text(encoding="utf-8").splitlines()]
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("exp018-kv")
    from eval.exp.exp020_resolution import _clear

    for arm in {r["arm"] for r in rows}:
        _clear("exp018-kv", "EXP-018", arm)
    for r in rows:
        metrics = {k: float(v) for k, v in r.items() if isinstance(v, int | float) and k != "trial"}
        with mlflow.start_run(run_name=f"EXP-018-{r['arm']}-t{r['trial']}"):
            mlflow.set_tags({"exp": "EXP-018", "variant": r["arm"], "seed": str(r["trial"]),
                             "failure": r.get("failure", "")})  # fmt: skip
            mlflow.log_params({"model": VARIANT, "max_model_len": r.get("max_model_len"),
                               "kv_dtype": "fp8" if ARMS[r["arm"]][1] else "auto"})  # fmt: skip
            mlflow.log_metrics(metrics)
    typer.echo(f"logged {len(rows)} trials")


if __name__ == "__main__":
    app()
