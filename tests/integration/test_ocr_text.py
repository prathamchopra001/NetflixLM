"""Real PP-OCRv6 + GLiNER on Pillow-rendered keyframes: every on-screen type is detected.

gpu: hold data/gpu.lock while running it. Needs models/rapidocr/*.onnx and gliner-x-base in HF_HOME.
"""

import importlib.util
from pathlib import Path

import pytest
import yaml

from nip.agents.clearance.ocr_text import Keyframe, TextScanner, ocr_detections
from nip.runtime.clients.ner import GlinerBackend
from nip.runtime.clients.ocr import RapidOcrBackend

pytestmark = pytest.mark.gpu

FIX = Path(__file__).parents[1] / "fixtures" / "clearance"
CASES = yaml.safe_load((FIX / "cases.yaml").read_text("utf-8"))
spec = importlib.util.spec_from_file_location("clr_render", FIX / "render.py")
assert spec and spec.loader
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)


def test_every_type_is_detected_on_rendered_keyframes(tmp_path: Path) -> None:
    frames = []
    for i, c in enumerate(CASES):
        p = tmp_path / f"{i}_0.png"
        p.write_bytes(render.render([c["text"]]))
        frames.append(Keyframe(i, 0, p))
    rows = ocr_detections(frames, RapidOcrBackend())
    scanner = TextScanner(GlinerBackend(), fictional=["Brightwave Energy"])
    det = {"clr.phone", "clr.url", "clr.email", "clr.plate"}
    for i, c in enumerate(CASES):
        # candidates are per OCR line; the case's language picks Presidio's language
        got = {x.check for x in scanner.candidates([r for r in rows if r.shot == i], c["lang"])}
        want = set(c["expect"])
        where = (c["id"], [r.text for r in rows if r.shot == i], got)
        assert got & det == want & det, where  # rule-based recognizers: exact
        assert want <= got, where  # GLiNER must find what it is meant to find
        if c["id"] == "brand_fictional":  # the bible's brand must never come back
            assert "clr.brand_text" not in got, where
