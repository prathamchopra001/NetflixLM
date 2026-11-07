import json
from pathlib import Path
from typing import Any

import pytest

from eval.injectors.base import Target
from eval.metrics import Label, evaluate, load_labels, match, overlap, score
from nip.contracts import Flag

OWNER = {
    "loc": ("localization_auditor", "localization"),
    "plot": ("script_critic", "plot_hole"),
    "cont": ("continuity_inspector", "continuity"),
}


def flag(
    check: str = "loc.gender",
    frames: tuple[int, int] | None = (100, 200),
    *,
    ref: str = "r",
    scene: str | None = None,
    lang: str | None = "es",
    tier: str = "must_review",
    episode: str = "E1",
    judge: str = "n/a",
    ctx_frames: tuple[int, int] | None = (100, 200),
) -> Flag:
    agent, category = OWNER[check.split(".")[0]]
    ev: dict[str, Any] = {"kind": "subtitle_cue", "ref": ref, "role": "claim", "scene": scene}
    if frames:
        ev["frames"] = frames
    return Flag.model_validate(
        {
            "run_id": "r",
            "episode": episode,
            "agent": agent,
            "check": check,
            "category": category,
            "lang": lang,
            "severity": 3,
            "confidence": 0.9,
            "tier": tier,
            "title": "t",
            "explanation": "e",
            "evidence": [ev, {**ev, "ref": "other", "role": "context", "frames": ctx_frames}],
            "produced_by": {"model_variant": None, "plan_id": "p"},
            "verification": {"judge": judge},
        }
    )


def label(
    check: str = "loc.gender",
    frames: tuple[int, int] | None = (100, 200),
    *,
    refs: tuple[str, ...] = (),
    lang: str | None = "es",
    episode: str = "E1",
) -> Label:
    return Label(
        label_id="l",
        title="t",
        episode=episode,
        check=check,
        lang=lang,
        target=Target(kind="subtitle_cue", refs=list(refs), frames=frames),
        description="d",
        injector="test.v1",
        seed=0,
    )


def test_overlap_rules() -> None:
    assert overlap(flag(), label()) == 1.0
    assert overlap(flag(frames=(100, 140)), label()) == pytest.approx(0.4)  # IoU 40/100
    assert overlap(flag(frames=(150, 300)), label()) == 0.0  # IoU 50/200 = 0.25 < 0.3
    assert overlap(flag(frames=(200, 300)), label()) == 0.0  # half-open: touching is no overlap
    assert overlap(flag(lang="fr"), label()) == 0.0
    assert overlap(flag(lang=None), label()) == 1.0  # lang only compared when both are set
    assert overlap(flag(episode="E2"), label()) == 0.0
    assert overlap(flag("loc.term"), label()) == 0.0


def test_overlap_script_refs_and_equivalence() -> None:
    lb = label("plot.prop_provenance", None, refs=("E1/scene/4",), lang=None)
    assert overlap(flag("cont.prop_text", None, scene="E1/scene/4", lang=None), lb) == 1.0
    assert overlap(flag("cont.prop_text", None, scene="E1/scene/5", lang=None), lb) == 0.0
    assert overlap(flag("cont.wardrobe_text", None, scene="E1/scene/4", lang=None), lb) == 0.0


def test_matching_is_optimal_not_greedy() -> None:
    l1, l2 = label(frames=(0, 100)), label(frames=(90, 190))
    f1, f2 = flag(frames=(30, 150)), flag(frames=(0, 40))
    # f1 overlaps l1 best (0.47) but f2 can only match l1; the optimum is f1->l2, f2->l1.
    assert sorted(match([f1, f2], [l1, l2])) == [(0, 1), (1, 0)]


def test_one_to_one() -> None:
    sc = score([flag(), flag()], [label()])
    c = sc.counts["all"]
    assert (c.tp, c.fp, c.fn) == (1, 1, 0)


def test_counts_by_check_and_lang_with_native() -> None:
    flags = [flag(), flag("loc.term", (500, 600), lang="fr"), flag(frames=(900, 950))]
    labels = [label(), label("loc.term", (700, 800), lang="fr")]
    native = [label(frames=(900, 950))]
    sc = score(flags, labels, native)
    assert sc.outcomes == ["tp", "fp", "native"]
    assert (sc.counts["check/loc.gender"].tp, sc.counts["check/loc.gender"].native_tp) == (1, 1)
    assert sc.counts["check/loc.term"].fp == 1 and sc.counts["check/loc.term"].fn == 1
    assert sc.counts["lang/fr"].fn == 1 and sc.counts["lang/es"].tp == 1


def test_evaluate_shown_vs_all_and_verification_noise() -> None:
    flags = [
        flag(),  # TP, shown
        flag(frames=(500, 600), tier="review_recommended", judge="fail"),  # FP, shown, dropped
        flag(frames=(700, 800), tier="suppressed", judge="fail"),  # FP, hidden, dropped
        flag(frames=(300, 400), tier="suppressed"),  # TP of the second label, hidden
    ]
    labels = [label(), label(frames=(300, 400))]
    m = evaluate(
        flags, labels, content_hours=2.0, gpu_seconds=60.0, wall_seconds=30.0, coverage=1.0
    )
    assert m["shown/precision/all"] == 0.5 and m["shown/recall/all"] == 0.5
    assert m["shown/f1/check/loc.gender"] == 0.5
    assert m["all/precision/all"] == 0.5 and m["all/recall/all"] == 1.0
    assert m["all/f1/lang/es"] == pytest.approx(2 * 0.5 / 1.5)
    assert m["verification/fp_dropped_rate"] == 1.0 and m["verification/tp_dropped_rate"] == 0.0
    assert (
        m["noise/fp_per_hour"] == 0.5 and m["noise/fp_per_hour/agent/localization_auditor"] == 0.5
    )
    assert (m["cost/gpu_s_per_hour"], m["cost/wall_s_per_hour"], m["coverage"]) == (30.0, 15.0, 1.0)


def test_evaluate_empty() -> None:
    assert evaluate([], [])["verification/fp_dropped_rate"] == 0.0
    assert evaluate([], [label()])["all/recall/all"] == 0.0


def test_ref_does_not_bypass_iou_and_context_evidence_is_ignored() -> None:
    timed = label(frames=(100, 200), refs=("E1/es/1",))
    assert overlap(flag(frames=(500, 600), ref="E1/es/1"), timed) == 0.0  # same ref, disjoint
    assert overlap(flag(frames=None, ref="E1/es/1"), timed) == 0.0  # no frames: no IoU
    # claim evidence elsewhere, context evidence sitting on the label's frames / ref
    assert overlap(flag(frames=(500, 600), ctx_frames=(100, 200)), timed) == 0.0
    scripted = label("plot.prop_provenance", None, refs=("E1/sc/9",), lang=None)
    assert overlap(flag("cont.prop_text", None, ref="x", lang=None), scripted) == 0.0


def test_equivalence_match_is_attributed_per_side() -> None:
    f = flag("cont.prop_text", None, scene="E1/scene/4", lang=None)
    lb = label("plot.prop_provenance", None, refs=("E1/scene/4",), lang=None)
    m = evaluate([f], [lb])
    # precision is booked against the flag's check, recall against the label's check
    assert m["all/tp/check/cont.prop_text"] == 1 and m["all/precision/check/cont.prop_text"] == 1.0
    assert m["all/recall/check/cont.prop_text"] == 0.0
    assert m["all/found/check/plot.prop_provenance"] == 1
    assert m["all/recall/check/plot.prop_provenance"] == 1.0
    assert m["all/tp/check/plot.prop_provenance"] == 0
    assert m["all/precision/check/plot.prop_provenance"] == 0.0
    assert m["all/precision/all"] == 1.0 and m["all/recall/all"] == 1.0


@pytest.mark.parametrize(
    ("row", "error"),
    [
        ({"episode": None}, "episode"),  # never in the same match block as a flag
        ({"target": {"kind": "subtitle_file"}}, "refs or frames"),
        ({"target": {"kind": "subtitle_file", "refs": ["sintel_en.srt"]}}, "not an evidence ref"),
        ({"target": {"kind": "subtitle_cue", "refs": ["E2/es/4"]}}, "outside episode"),
    ],
)
def test_load_labels_refuses_labels_that_can_never_match(
    tmp_path: Path, row: dict[str, Any], error: str
) -> None:
    good = label(refs=("E1/es/4",)).model_dump(mode="json")
    p = tmp_path / "l.jsonl"
    p.write_text(json.dumps(good) + "\n" + json.dumps({**good, **row}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=rf"l\.jsonl:2: invalid label(.|\n)*{error}"):
        load_labels(p)
    p.write_text(json.dumps(good) + "\n", encoding="utf-8")
    assert load_labels(p) == [label(refs=("E1/es/4",))]
