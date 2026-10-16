"""Serve applications from the laptop Plan; deploy/teardown/staged loop against a fake Serve."""

import json
import signal
from pathlib import Path
from typing import Any

import pytest

from nip.contracts import Autoscaling, Gpu, HardwareInventory, Node, Slot, StageGroup
from nip.runtime import serving
from nip.runtime.catalog import load_catalog
from nip.runtime.planner import plan
from nip.runtime.serving import (
    App,
    Placeholder,
    ServingError,
    VllmServer,
    apps,
    deploy,
    run,
    teardown,
    vllm_args,
)

CATALOG = load_catalog(Path(__file__).parents[3] / "config" / "catalog.yaml")


def _inv(total: float, free: float) -> HardwareInventory:
    gpu = Gpu(index=0, name="gpu", vram_total_gb=total, vram_free_gb=free, compute_capability="8.9")
    return HardwareInventory(
        fingerprint="sim",
        nodes=[Node(node_id="n0", cpus=16, ram_gb=31.0, gpus=[gpu])],
        autoscaling=Autoscaling(enabled=False, max_gpu_nodes=0),
    )


LAPTOP = _inv(8.0, 7.15)
UNITS = {s: 10 for s in Slot}
PLAN = plan(LAPTOP, CATALOG, UNITS)


class _Dep:
    def __init__(self, cls: type) -> None:
        self.cls, self.opts = cls, {}

    def options(self, **kw: Any) -> "_Dep":
        self.opts = kw
        return self

    def bind(self, *args: Any) -> dict[str, Any]:
        return {"cls": self.cls, "opts": self.opts, "args": args}


class FakeServe:
    def __init__(self, fail: tuple[str, ...] = ()) -> None:
        self.fail, self.running, self.log = fail, {}, []

    def deployment(self, cls: type) -> _Dep:
        return _Dep(cls)

    def run(self, app: dict[str, Any], name: str, route_prefix: str) -> None:
        self.log.append(("run", name))
        if name in self.fail:
            raise RuntimeError("replica failed to start")
        self.running[name] = app

    def delete(self, name: str) -> None:
        self.log.append(("delete", name))
        self.running.pop(name, None)


def test_laptop_llm_group_is_one_shared_vllm_app() -> None:
    [a] = apps(PLAN, CATALOG, LAPTOP, [Slot.VLM, Slot.TEXT_LLM])
    assert (a.name, a.route_prefix) == ("nip-qwen3.5-4b-awq", "/models/qwen3.5-4b-awq")
    assert a.slots == (Slot.VLM, Slot.TEXT_LLM) and a.replicas == 1
    assert a.num_gpus == PLAN.decisions[Slot.TEXT_LLM].gpu_fraction == 0.79
    args = list(a.vllm_args)
    assert args[0] == "cyankiwi/Qwen3.5-4B-AWQ-4bit"  # the AWQ checkpoint, not the bf16 base
    opt = {k: v for k, v in zip(args, args[1:], strict=False) if k.startswith("--")}
    assert opt["--served-model-name"] == "qwen3.5-4b-awq"
    assert opt["--max-model-len"] == "16384" and opt["--gpu-memory-utilization"] == "0.79"
    assert opt["--kv-cache-memory-bytes"] == str(2170 * 2**20)  # the Plan's exact KV budget
    assert opt["--tensor-parallel-size"] == "1" and opt["--limit-mm-per-prompt.image"] == "2"
    assert json.loads(args[args.index("--mm-processor-kwargs") + 1]) == {"max_pixels": 589824}
    assert "--enforce-eager" in args  # 8 GB is a small GPU


def test_big_gpu_keeps_cuda_graphs_and_actor_apps_get_fractions() -> None:
    big = _inv(47.99, 47.4)
    p = plan(big, CATALOG, UNITS)
    llm = [a for g in p.groups for a in apps(p, CATALOG, big, g.slots) if a.vllm_args]
    assert llm and all("--enforce-eager" not in a.vllm_args for a in llm)
    timeline = apps(PLAN, CATALOG, LAPTOP, [Slot.SHOT_DETECTOR, Slot.ASR])
    assert [(a.variant, a.vllm_args) for a in timeline] == [
        ("transnetv2", ()),
        ("faster-whisper-large-v3-int8", ()),
    ]
    assert all(0 < a.num_gpus < 1 for a in timeline)


def test_stub_plan_deploys_nothing() -> None:
    p = plan(LAPTOP, CATALOG, UNITS, stub=True)
    assert apps(p, CATALOG, LAPTOP, p.groups[0].slots) == []


def test_deploy_binds_options_and_redeploy_scales_in_place() -> None:
    serve = FakeServe()
    a = App("m", (Slot.ASR,), 1, 0.3)
    deploy([a], serve)
    app = serve.running["nip-m"]
    assert app["cls"] is Placeholder and app["args"] == ("m",)
    assert app["opts"]["ray_actor_options"] == {"num_gpus": 0.3}
    assert app["opts"]["max_constructor_retry_count"] == 1
    deploy([App("m", (Slot.ASR,), 3, 0.3)], serve)
    assert serve.running["nip-m"]["opts"]["num_replicas"] == 3 and len(serve.running) == 1
    v = App("q", (Slot.TEXT_LLM,), 1, 0.77, ("repo", "--x"))
    deploy([v], serve)
    assert serve.running["nip-q"]["cls"] is VllmServer
    assert serve.running["nip-q"]["args"] == ("q", ["repo", "--x"], "/models/q")


def test_deploy_failure_raises_serving_error() -> None:
    with pytest.raises(ServingError, match="nip-m failed"):
        deploy([App("m", (Slot.ASR,), 1, 0.3)], FakeServe(fail=("nip-m",)))


def test_teardown_waits_for_vram_back_to_idle() -> None:
    serve, readings = FakeServe(), iter([6000, 3000, 1600])
    deploy([App("m", (Slot.ASR,), 1, 0.3)], serve)
    teardown([App("m", (Slot.ASR,), 1, 0.3)], serve, idle_mib=1500, used_mib=lambda: next(readings))
    assert serve.running == {}
    with pytest.raises(ServingError, match="after teardown"):
        teardown([], serve, idle_mib=1500, used_mib=lambda: 2500, timeout_s=0.0)


def test_staged_run_loads_each_group_then_unloads_it() -> None:
    serve, done = FakeServe(), []

    def work(g: StageGroup) -> None:
        names = {a.name for a in apps(PLAN, CATALOG, LAPTOP, g.slots)}
        assert set(serve.running) == names  # only this group is up
        done.append(g.name)

    out = run(PLAN, CATALOG, LAPTOP, work, serve, used_mib=lambda: 1500)
    assert done == [g.name for g in PLAN.groups] and len(done) == 5
    assert serve.running == {} and [o["group"] for o in out] == done
    assert serve.log.count(("run", "nip-qwen3.5-4b-awq")) == 1  # one load for vlm+llm


def test_failed_deploy_still_tears_down_the_group() -> None:
    serve = FakeServe(fail=("nip-faster-whisper-large-v3-int8",))
    with pytest.raises(ServingError):
        run(PLAN, CATALOG, LAPTOP, lambda g: None, serve, used_mib=lambda: 1500)
    assert serve.running == {}


def test_vllm_args_reject_an_incomplete_decision() -> None:
    v = next(v for v in CATALOG.variants if v.id == "qwen3.5-4b-awq")
    d = PLAN.decisions[Slot.TEXT_LLM].model_copy(update={"context": None})
    with pytest.raises(ServingError, match="lacks"):
        vllm_args(v, d, None, eager=True)


class _Proc:
    pid = 4242

    def poll(self) -> int | None:
        return 0


def _stop(monkeypatch: pytest.MonkeyPatch, running_checks: int) -> list[int]:
    """stop() against a group that still runs for `running_checks` liveness checks."""
    sent: list[int] = []
    checks = iter([True] * running_checks + [False])

    def kill(pid: int, sig: int) -> None:
        assert pid == -4242  # always the process group, never just the leader
        sent.append(sig)

    monkeypatch.setattr(serving.os, "kill", kill)
    monkeypatch.setattr(serving, "_group_running", lambda pgid: next(checks))
    monkeypatch.setattr(serving.time, "sleep", lambda s: None)
    srv = VllmServer.__new__(VllmServer)
    srv.proc = _Proc()  # type: ignore[assignment]
    try:
        srv.stop(timeout_s=0.0 if running_checks > 5 else 60.0)
    finally:
        del srv.proc  # keep __del__ from signalling for real
    return sent


def test_stop_kills_the_group_even_after_vllm_serve_exited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The leader has exited (poll() == 0), EngineCore runs on for two checks, then exits.
    assert _stop(monkeypatch, running_checks=2) == [signal.SIGTERM]


def test_stop_sigkills_a_group_that_ignores_sigterm(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _stop(monkeypatch, running_checks=10) == [signal.SIGTERM, 9]


def test_group_running_ignores_zombies_and_other_groups(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for pid, stat in {"7": "7 (python3) Z 1 794 794", "8": "8 (ray) S 0 1 1"}.items():
        (tmp_path / pid).mkdir()
        (tmp_path / pid / "stat").write_text(stat)
    real_path = serving.Path
    monkeypatch.setattr(serving, "Path", lambda p: tmp_path if p == "/proc" else real_path(p))
    assert not serving._group_running(794)  # only a zombie left
    assert serving._group_running(1)


def test_run_keeps_the_deploy_error_when_teardown_also_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = iter(range(0, 10**9, 60))  # each reading 60 s later: teardown's 120 s wait ends fast
    monkeypatch.setattr(serving.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(serving.time, "sleep", lambda s: None)
    serve = FakeServe(fail=("nip-faster-whisper-large-v3-int8",))
    readings = iter([1500] + [9000] * 10**6)  # idle, then VRAM never comes back
    with pytest.raises(ServingError, match="failed to deploy") as e:
        run(PLAN, CATALOG, LAPTOP, lambda g: None, serve, used_mib=lambda: next(readings))
    assert any("after teardown" in n for n in e.value.__notes__)
