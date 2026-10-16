"""Serve applications from the laptop Plan; deploy/teardown/staged loop against a fake Serve."""

import json
from pathlib import Path
from typing import Any

import pytest

from nip.contracts import Autoscaling, Gpu, HardwareInventory, Node, Slot, StageGroup
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
    assert a.num_gpus == PLAN.decisions[Slot.TEXT_LLM].gpu_fraction == 0.77
    args = list(a.vllm_args)
    assert args[0] == "Qwen/Qwen3.5-4B"
    opt = {k: v for k, v in zip(args, args[1:], strict=False) if k.startswith("--")}
    assert opt["--served-model-name"] == "qwen3.5-4b-awq"
    assert opt["--max-model-len"] == "8192" and opt["--gpu-memory-utilization"] == "0.77"
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
