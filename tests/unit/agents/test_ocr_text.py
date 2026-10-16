"""Clearance on-screen text: typed candidates per check id, fiction allow-lists, OCR -> rows."""

import importlib.util
from pathlib import Path

import pytest
import yaml
from sqlalchemy import insert
from sqlalchemy.dialects import postgresql

from nip.agents.clearance.ocr_text import (
    Detection,
    Keyframe,
    TextScanner,
    clean_ocr_urls,
    insert_detections,
    ocr_detections,
)
from nip.runtime.clients.ner import Entity, StubNER
from nip.runtime.clients.ocr import OcrLine, StubOCR, fingerprint
from nip.store.schema import detection

FIX = Path(__file__).parents[2] / "fixtures" / "clearance"
CASES = yaml.safe_load((FIX / "cases.yaml").read_text("utf-8"))
spec = importlib.util.spec_from_file_location("clr_render", FIX / "render.py")
assert spec and spec.loader
render_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_mod)

FICTIONAL = ["Brightwave Energy"]


def det(text: str, shot: int = 3, n: int = 1, conf: float = 0.96) -> Detection:
    return Detection(shot, n, text, (0.1, 0.2, 0.3, 0.05), conf, "pp-ocrv6-medium")


@pytest.fixture(scope="module")
def scanner() -> TextScanner:
    recorded = {c["text"]: [Entity(**e) for e in c["ner"]] for c in CASES if "ner" in c}
    return TextScanner(StubNER(recorded), fictional=FICTIONAL)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_candidates_per_check(scanner: TextScanner, case: dict[str, object]) -> None:
    got = [c.check for c in scanner.candidates([det(str(case["text"]))], str(case["lang"]))]
    assert sorted(got) == sorted(case["expect"])  # type: ignore[arg-type]


def test_candidate_carries_where_it_was_seen(scanner: TextScanner) -> None:
    (c,) = scanner.candidates([det("CALL (617) 482-9154 NOW", shot=7, n=2, conf=0.9)])
    assert (c.check, c.text, c.shot, c.n, c.box) == (
        "clr.phone",
        "(617) 482-9154",
        7,
        2,
        (0.1, 0.2, 0.3, 0.05),
    )
    assert c.line == "CALL (617) 482-9154 NOW" and c.ocr_confidence == 0.9
    assert c.confidence == round(0.9 * c.score, 4)


def test_domain_inside_an_email_is_not_a_second_url(scanner: TextScanner) -> None:
    got = scanner.candidates([det("write to bob@realco.com")])
    assert [c.check for c in got] == ["clr.email"]


def test_es_fr_run_without_gpl_spacy_models() -> None:
    for gpl in ("es_core_news_sm", "fr_core_news_sm"):
        assert importlib.util.find_spec(gpl) is None  # never installed (license policy)
    s = TextScanner()  # also runs with no NER at all
    assert [c.check for c in s.candidates([det("Llame al 912 345 678")], "es")] == ["clr.phone"]
    assert [c.check for c in s.candidates([det("Appelez le 01 23 45 67 89")], "fr")] == [
        "clr.phone"
    ]
    assert s.candidates([det("Brightwave Energy")], "fr") == []


def test_deny_brands_from_the_clearance_log_are_candidates() -> None:
    s = TextScanner(deny_brands=["Duff Beer"], fictional=["Brightwave Energy"])
    assert [c.check for c in s.candidates([det("DUFF BEER")])] == ["clr.brand_text"]


def test_fictional_brand_is_dropped_but_a_real_one_with_it_is_kept() -> None:
    ner = StubNER(
        {
            "Brightwave Energy and Nike": [
                Entity(text="Brightwave Energy", label="organization", start=0, end=17, score=0.9),
                Entity(text="Nike", label="organization", start=22, end=26, score=0.9),
            ]
        }
    )
    s = TextScanner(ner, fictional=FICTIONAL)
    got = s.candidates([det("Brightwave Energy and Nike")])
    assert [c.text for c in got] == ["Nike"]


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("www . acme-shop . com", "www.acme-shop.com"),
        ("visit site .com now", "visit site.com now"),
        ("shop. io/new", "shop.io/new"),
        ("https : / / foo.org", "https://foo.org"),
        ("Hello. World is here", "Hello. World is here"),  # prose keeps its sentence break
        ("Hello. It works", "Hello. It works"),
        ("Wait . Now", "Wait . Now"),
        ("no urls here", "no urls here"),
    ],
)
def test_clean_ocr_urls(raw: str, clean: str) -> None:
    assert clean_ocr_urls(raw) == clean


def test_ocr_detections_are_rows_of_the_frames_text(tmp_path: Path) -> None:
    img = render_mod.render(["CALL (617) 482-9154"])
    (tmp_path / "4_0.png").write_bytes(img)
    (tmp_path / "4_1.png").write_bytes(render_mod.render(["other"]))
    hello = OcrLine(text="HELLO", box=(0.1, 0.1, 0.2, 0.05), confidence=0.97)
    frames = [Keyframe(4, 0, tmp_path / "4_0.png"), Keyframe(4, 1, tmp_path / "4_1.png")]
    rows = ocr_detections(frames, StubOCR({fingerprint(img): [hello]}))
    assert rows == [Detection(4, 0, "HELLO", (0.1, 0.1, 0.2, 0.05), 0.97, "pp-ocrv6-medium")]
    assert rows[0].channel == "ocr" and rows[0].label == "text"
    assert img[:4] == b"\x89PNG"


def test_insert_detections_statement_matches_the_detection_table() -> None:
    class Conn:
        def __init__(self) -> None:
            self.calls: list[tuple[object, list[dict[str, object]]]] = []

        def execute(self, stmt: object, values: list[dict[str, object]]) -> None:
            self.calls.append((stmt, values))

    conn = Conn()
    n = insert_detections(conn, 9, {3: 31}, [det("HELLO"), det("X", shot=5)])  # type: ignore[arg-type]
    ((stmt, values),) = conn.calls
    assert n == 2 and str(stmt.compile(dialect=postgresql.dialect())) == str(  # type: ignore[attr-defined]
        insert(detection).compile(dialect=postgresql.dialect())
    )
    assert values[0] == {
        "episode_id": 9,
        "shot_id": 31,
        "keyframe_n": 1,
        "channel": "ocr",
        "label": "text",
        "text": "HELLO",
        "box": [0.1, 0.2, 0.3, 0.05],
        "confidence": 0.96,
        "model_variant": "pp-ocrv6-medium",
    }
    assert values[1]["shot_id"] is None  # a shot index the store has no id for
