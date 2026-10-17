"""Clearance occurrences: gap merge, screen time from keyframe cells, prominence, severity."""

import logging
from fractions import Fraction
from typing import Any

import cv2
import numpy as np
import pytest

from nip.agents.clearance.matching import Item, Registry
from nip.agents.clearance.occurrences import Hit, analyze, sharpness
from nip.config import pipeline_config
from nip.contracts import refs
from nip.contracts.flag import EvidenceKind
from nip.contracts.timeline import Span, Timeline
from nip.timecode import frame_to_smpte

CFG: dict[str, Any] = pipeline_config()["clearance"]
FPS = Fraction(24)
GAP = round(CFG["occurrence_gap_s"] * 24)  # 48 frames
BIG = (0.3, 0.4, 0.2, 0.1)  # area 0.02, centred
SMALL = (0.02, 0.02, 0.05, 0.02)  # area 0.001, in a corner


def timeline(shots: list[tuple[int, int]], kfs: list[tuple[int, int, int]]) -> Timeline:
    """24 fps picture; `kfs` are (shot index, n, frame)."""

    def span(kind: EvidenceKind, ref: str, a: int, b: int) -> Span:
        t = [frame_to_smpte(x, FPS) for x in (a, b)]
        return Span(kind=kind, ref=ref, frames=(a, b), tc_in=t[0], tc_out=t[1])

    spans = [span(EvidenceKind.SHOT, refs.shot("S01E01", i), a, b) for i, (a, b) in enumerate(shots)]
    spans += [span(EvidenceKind.KEYFRAME, refs.keyframe("S01E01", i, n), f, f + 1) for i, n, f in kfs]
    return Timeline(episode="S01E01", fps=(24, 1), duration_frames=shots[-1][1], spans=tuple(spans))


def hit(shot: int, n: int = 0, text: str = "(617) 482-9154", **kw: Any) -> Hit:
    base: dict[str, Any] = {
        "check": "clr.phone", "text": text, "shot": shot, "n": n, "box": BIG,
        "confidence": 0.9, "model_variant": "pp-ocrv6-medium", "sharpness": 300.0,
    }  # fmt: skip
    return Hit(**{**base, **kw})


def two_shots(second_start: int) -> Timeline:
    """Shot 0 = [0, 48) with its keyframe at 24, shot 1 = [second_start, +48) with its at +24."""
    s = second_start
    return timeline([(0, 48), (s, s + 48)], [(0, 0, 24), (1, 0, s + 24)])


def test_gap_of_exactly_two_seconds_merges_and_one_frame_more_splits() -> None:
    reg = Registry()
    merged = analyze([hit(0), hit(1)], reg, two_shots(48 + GAP), CFG)
    assert len(merged) == 1
    (o,) = merged
    assert o.shots == (0, 1) and o.frames == (0, 48 + GAP + 48)
    assert o.screen_frames == 96  # the two cells; the gap between them is not screen time
    split = analyze([hit(0), hit(1)], reg, two_shots(48 + GAP + 1), CFG)
    assert [o.shots for o in split] == [(0,), (1,)]


def test_same_text_in_the_same_shot_is_one_occurrence_with_its_cells_added() -> None:
    tl = timeline([(0, 240)], [(0, 0, 60), (0, 1, 180)])
    (o,) = analyze([hit(0, 0), hit(0, 1)], Registry(), tl, CFG)
    # cells [0, 120) and [120, 240), each capped at 4 s = 96 frames centred on the keyframe
    assert o.screen_frames == 2 * 96 and o.frames == (12, 228)


def test_a_cell_is_capped_so_a_long_shot_does_not_claim_all_of_it() -> None:
    tl = timeline([(0, 2400)], [(0, 0, 1200)])
    (o,) = analyze([hit(0)], Registry(), tl, CFG)
    assert o.screen_frames == 96 and o.frames == (1152, 1248)


def test_different_text_or_item_never_merges() -> None:
    tl = two_shots(48)
    occs = analyze([hit(0, text="(617) 482-9154"), hit(1, text="(617) 482-9155")], Registry(), tl, CFG)
    assert len(occs) == 2
    # two spellings of one logged item are one occurrence
    reg = Registry((Item(7, "(617) 482-9154", "phone", "pending"),))
    (o,) = analyze([hit(0, text="(617) 482-9154"), hit(1, text="617.482.9154")], reg, tl, CFG)
    assert o.match.item is not None and o.match.item.id == 7 and len(o.hits) == 2


def test_fictional_text_is_dropped_and_a_missing_keyframe_is_skipped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    reg = Registry(fictional=("Kappa Cola",))
    tl = two_shots(48)
    with caplog.at_level(logging.WARNING):
        occs = analyze(
            [hit(0, text="KAPPA COLA", check="clr.brand_text"), hit(5, n=3)], reg, tl, CFG
        )
    assert occs == [] and "no such keyframe" in caplog.text


def test_prominence_grows_with_size_centrality_sharpness_and_duration() -> None:
    tl = timeline([(0, 48), (1000, 1480)], [(0, 0, 24), (1, 0, 1240)])
    reg = Registry()

    def score(**kw: Any) -> float:
        return analyze([hit(0, **kw)], reg, tl, CFG)[0].prominence

    base = score(box=SMALL, sharpness=10.0)
    assert score(box=BIG, sharpness=10.0) > base  # larger and more central
    assert score(box=SMALL, sharpness=300.0) > base  # sharper
    assert score(box=SMALL, sharpness=None) > base  # unknown sharpness counts as middling
    longer = analyze([hit(1, box=SMALL, sharpness=10.0)], reg, tl, CFG)[0]
    assert longer.screen_frames == 96 > 48 and longer.prominence > base  # more screen time


def test_featured_and_background_drive_severity_of_unknown_items_only() -> None:
    tl = timeline([(0, 96)], [(0, 0, 48)])
    sev = CFG["severity"]
    prom = CFG["prominence"]
    (big,) = analyze([hit(0, box=BIG)], Registry(), tl, CFG)
    (small,) = analyze([hit(0, box=SMALL, sharpness=5.0)], Registry(), tl, CFG)
    assert big.featured and big.prominence >= prom["featured_min"]
    assert not small.featured and small.prominence < prom["featured_min"]
    assert (big.severity, small.severity) == (sev["featured"], sev["background"])
    # pending / denied are high whatever the prominence
    log = Registry((Item(1, "(617) 482-9154", "phone", "pending"),))
    (p,) = analyze([hit(0, box=SMALL, sharpness=5.0)], log, tl, CFG)
    assert not p.featured and p.severity == sev["pending"] >= 4
    log = Registry((Item(1, "(617) 482-9154", "phone", "denied"),))
    (d,) = analyze([hit(0, box=SMALL, sharpness=5.0)], log, tl, CFG)
    assert d.severity == sev["denied"] == 5


def test_the_best_view_is_the_evidence_keyframe() -> None:
    tl = timeline([(0, 240)], [(0, 0, 60), (0, 1, 180)])
    worse, better = hit(0, 0, box=SMALL, sharpness=5.0), hit(0, 1, box=BIG, sharpness=300.0)
    (o,) = analyze([worse, better], Registry(), tl, CFG)
    assert o.best == better and o.confidence == 0.9


def test_sharpness_is_higher_for_crisp_text_than_for_blurred() -> None:
    img = np.full((200, 400, 3), 30, np.uint8)
    cv2.putText(img, "555 0142", (40, 120), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
    sharp = cv2.imencode(".png", img)[1].tobytes()
    blur = cv2.imencode(".png", cv2.GaussianBlur(img, (0, 0), 4))[1].tobytes()
    box = (0.05, 0.25, 0.9, 0.5)
    assert sharpness(sharp, box) > 10 * sharpness(blur, box) > 0
