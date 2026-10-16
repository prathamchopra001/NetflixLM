"""Ray Serve deploy/teardown on the live cluster. Runs inside ray-head (Ray is Linux-only):

  docker compose -f compose.yaml -f eval/exp/exp001.compose.yaml exec ray-head \
      python3 -m pytest -p no:cacheprovider /app/tests/integration/test_serving.py
"""

import io
import json
import urllib.request
from enum import StrEnum

import pytest
from pydantic import BaseModel

from nip.contracts import Autoscaling, Gpu, HardwareInventory, Node, Slot, StageGroup
from nip.runtime.catalog import load_catalog
from nip.runtime.clients import SERVE_URL, llm
from nip.runtime.planner import plan
from nip.runtime.serving import App, apps, deploy, gpu_used_mib, ray_serve, run, teardown

pytest.importorskip("ray")
pytestmark = pytest.mark.integration

# The catalog has no checkpoint for qwen3.5-4b-awq yet (proposal in notes/1.7.md).
CHECKPOINT = "cyankiwi/Qwen3.5-4B-AWQ-4bit"


def test_placeholder_app_answers_and_is_deleted() -> None:
    serve = ray_serve()
    a = App("it-placeholder", (Slot.ASR,), 1, 0.05)
    deploy([a], serve)
    with urllib.request.urlopen(f"{SERVE_URL}{a.route_prefix}", timeout=10) as r:
        assert json.load(r) == {"variant": "it-placeholder", "stub": True}
    teardown([a], serve)
    assert a.name not in serve.status().applications


class Color(StrEnum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class Answer(BaseModel):
    color: Color


@pytest.mark.gpu
def test_laptop_staged_plan_loads_each_group_and_returns_vram_to_idle() -> None:
    """The laptop Plan without the judge (its weights aren't downloaded): actor groups as
    placeholders, then the shared qwen model answers structured vlm/text_llm calls."""
    from PIL import Image

    base = load_catalog()
    catalog = base.model_copy(
        update={
            "variants": [
                v.model_copy(update={"checkpoint": CHECKPOINT}) if v.id == "qwen3.5-4b-awq" else v
                for v in base.variants
            ]
        }
    )
    gpu = Gpu(index=0, name="g", vram_total_gb=8.0, vram_free_gb=7.15, compute_capability="8.9")
    inv = HardwareInventory(
        fingerprint="laptop",
        nodes=[Node(node_id="n0", cpus=6, ram_gb=27.0, gpus=[gpu])],
        autoscaling=Autoscaling(enabled=False, max_gpu_nodes=0),
    )
    p = plan(inv, catalog, {s: 10 for s in Slot if s is not Slot.JUDGE_LLM})
    assert [g.name for g in p.groups] == ["timeline", "vision_prep", "text_prep", "vlm+llm"]
    serve = ray_serve()
    png = io.BytesIO()
    Image.new("RGB", (64, 64), (220, 20, 20)).save(png, "PNG")
    got: list[Answer] = []
    up: list[list[str]] = []

    def work(g: StageGroup) -> None:
        group = apps(p, catalog, inv, g.slots)
        up.append(sorted(serve.status().applications))
        assert set(up[-1]) == {a.name for a in group}  # only this group is loaded
        if Slot.TEXT_LLM not in g.slots:
            return
        c = llm(p, catalog, Slot.VLM)
        got.append(
            c.complete("What color is the square? /no_think", Answer, images=[png.getvalue()])
        )
        got.append(llm(p, catalog, Slot.TEXT_LLM).complete("Name the color of blood.", Answer))

    idle = gpu_used_mib()
    out = run(p, catalog, inv, work, serve)  # each teardown waits for VRAM back to idle
    print(out, up)
    assert [x.color for x in got] == [Color.RED, Color.RED]
    assert not serve.status().applications
    assert gpu_used_mib() <= idle + 256
