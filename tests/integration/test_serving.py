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

from nip.contracts import Slot, StageGroup
from nip.runtime.catalog import load_catalog
from nip.runtime.clients import SERVE_URL, llm
from nip.runtime.planner import plan
from nip.runtime.probe import probe
from nip.runtime.serving import App, apps, deploy, gpu_used_mib, ray_serve, run, teardown

pytest.importorskip("ray")
pytestmark = pytest.mark.integration


def test_placeholder_app_answers_and_is_deleted() -> None:
    serve = ray_serve()
    # a slot with no clients/<slot>.py Actor (asr, ocr, ner, text_embedder have one: serving._bind)
    a = App("it-placeholder", (Slot.DETECTOR,), 1, 0.05)
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
    """The Plan for this machine's probe (stock catalog, exact KV budget) without the judge (its
    weights aren't downloaded): actor groups as placeholders, then the shared qwen model answers
    structured vlm/text_llm calls."""
    from PIL import Image

    catalog = load_catalog()
    inv = probe()  # free VRAM as NVML reports it, Windows desktop included
    p = plan(inv, catalog, {s: 10 for s in Slot if s is not Slot.JUDGE_LLM})
    if Slot.TEXT_LLM in p.skipped_slots:
        pytest.skip(f"not enough free VRAM for the LLM right now: {p.warnings}")
    assert {Slot.TEXT_LLM, Slot.VLM} <= set(p.groups[-1].slots)
    [qwen] = [a for a in apps(p, catalog, inv, p.groups[-1].slots) if a.vllm_args]
    assert qwen.vllm_args[0] == "cyankiwi/Qwen3.5-4B-AWQ-4bit"
    assert "--kv-cache-memory-bytes" in qwen.vllm_args
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
