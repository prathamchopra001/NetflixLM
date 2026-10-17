"""Clearance flags and report: routing per status (pending/denied never hidden), evidence that
verifies and scores against a frame-range label, the CSV and its round trip."""

from fractions import Fraction
from typing import Any

import pytest

from eval.injectors.base import Label, Target
from eval.metrics import SHOWN, match
from nip.agents.base import Input, run_check
from nip.agents.clearance import CHECKS, ClrPhone
from nip.agents.clearance.checks import ClearanceText, ClrBrandText
from nip.agents.clearance.matching import Item, Registry
from nip.agents.clearance.occurrences import Hit, analyze
from nip.agents.clearance.ocr_text import Detection
from nip.agents.clearance.report import COLUMNS, from_csv, occurrence_rows, to_csv
from nip.agents.clearance.stage import Scan, with_ocr
from nip.config import pipeline_config
from nip.contracts import refs
from nip.contracts.flag import EvidenceKind, EvidenceRole, Flag, ProducedBy, Tier
from nip.contracts.timeline import Span, Timeline
from nip.timecode import frame_to_smpte
from nip.verification.verify import verify

CFG: dict[str, Any] = pipeline_config()["clearance"]
PB = ProducedBy(model_variant="pp-ocrv6-medium", plan_id="plan_1")
TEXT = "(212) 555-0234"
LOG = Registry(
    (
        Item(1, TEXT, "phone", "pending"),
        Item(2, "(415) 555-2671", "phone", "cleared"),
        Item(3, "7KLM482", "plate", "denied"),
    ),
    fictional=("Kappa Cola",),
)


KFS = [(0, 0, 48), (1, 0, 144), (2, 0, 240)]  # (shot, n, frame): the middle of each shot


def timeline(texts: dict[tuple[int, int], str], items: tuple[Item, ...] = LOG.items) -> Timeline:
    """Shots [0, 96), [96, 192), [192, 288) at 24 fps, one keyframe each; the clearance items as
    `clr/{id}` spans. As after the OCR stage: a keyframe stands for its cell and has its text."""
    shots = [(0, 96), (96, 192), (192, 288)]
    spans = [
        Span(kind=EvidenceKind.SHOT, ref=refs.shot("S01E01", i), frames=s,
             tc_in=frame_to_smpte(s[0], Fraction(24)), tc_out=frame_to_smpte(s[1], Fraction(24)))
        for i, s in enumerate(shots)
    ]  # fmt: skip
    for i, n, f in KFS:
        spans.append(
            Span(kind=EvidenceKind.KEYFRAME, ref=refs.keyframe("S01E01", i, n), frames=(f, f + 1),
                 tc_in=frame_to_smpte(f, Fraction(24)), tc_out=frame_to_smpte(f + 1, Fraction(24)))
        )  # fmt: skip
    spans += [Span(kind=EvidenceKind.CLEARANCE_ITEM, ref=f"clr/{i.id}", text=i.name) for i in items]
    tl = Timeline(episode="S01E01", fps=(24, 1), duration_frames=288, spans=tuple(spans))
    box = (0.3, 0.4, 0.2, 0.1)
    scans = {
        k: Scan([Detection(*k, t, box, 0.9, "pp-ocrv6-medium")], [], []) for k, t in texts.items()
    }
    return with_ocr(tl, scans, CFG)


def hit(check: str, text: str, shot: int, conf: float = 0.95, **kw: Any) -> Hit:
    return Hit(check, text, shot, 0, (0.3, 0.4, 0.2, 0.1), conf, "pp-ocrv6-medium", 300.0, **kw)


def flags_of(hits: list[Hit], tl: Timeline, check: type[ClearanceText] = ClrPhone) -> list[Flag]:
    c = check(hits=hits, registry=LOG, keyframes=KFS, cfg=CFG)
    return run_check(c, tl, "run_1", PB)


def test_checks_list_and_activation() -> None:
    assert [str(c.check) for c in CHECKS] == [
        "clr.phone", "clr.url", "clr.email", "clr.address", "clr.plate", "clr.brand_text",
    ]  # fmt: skip
    assert all(c.active({Input.PICTURE}) and not c.active({Input.SCRIPT}) for c in CHECKS)


def test_each_status_routes_as_the_architecture_says() -> None:
    tl = timeline({(0, 0): TEXT, (1, 0): "(415) 555-2671", (2, 0): "(617) 482-9154"})
    got = {
        f.evidence[0].ref: f  # the keyframe
        for f in flags_of(
            [
                hit("clr.phone", TEXT, 0),
                hit("clr.phone", "(415) 555-2671", 1),
                hit("clr.phone", "(617) 482-9154", 2),
            ],
            tl,
        )
    }
    pending, cleared, unknown = (got[refs.keyframe("S01E01", i, 0)] for i in range(3))
    assert (pending.tier, pending.severity) == (Tier.MUST_REVIEW, CFG["severity"]["pending"])
    assert cleared.tier is Tier.SUPPRESSED and cleared.suggested_fix is None  # kept for the audit
    assert unknown.tier is Tier.MUST_REVIEW and unknown.severity == CFG["severity"]["featured"]
    assert "not in the clearance log" in unknown.explanation
    assert any(e.ref == "clr/1" and e.role is EvidenceRole.CONTEXT for e in pending.evidence)
    assert all(e.kind is not EvidenceKind.CLEARANCE_ITEM for e in unknown.evidence)
    # a fictional name is not a clearance item: no flag at all
    assert not flags_of([hit("clr.brand_text", "KAPPA COLA", 0)], tl, ClrBrandText)


@pytest.mark.parametrize("confidence", [0.0, 0.01, 0.3, 0.69, 0.7, 0.95, 1.0])
@pytest.mark.parametrize(("check", "text", "status"), [
    ("clr.phone", TEXT, "pending"),
    ("clr.plate", "7KLM482", "denied"),
])  # fmt: skip
def test_pending_and_denied_are_never_hidden(
    check: str, text: str, status: str, confidence: float
) -> None:
    tl = timeline({(0, 0): text})
    cls = next(c for c in CHECKS if str(c.check) == check)
    (flag,) = flags_of([hit(check, text, 0, confidence)], tl, cls)
    assert flag.tier is Tier.MUST_REVIEW and flag.tier in SHOWN
    assert flag.severity >= 4 and flag.confidence == confidence


def test_an_unknown_item_is_routed_by_confidence() -> None:
    tl = timeline({(0, 0): "(617) 482-9154"})
    low, high = (
        flags_of([hit("clr.phone", "(617) 482-9154", 0, c)], tl)[0].tier for c in (0.5, 0.95)
    )
    assert (low, high) == (Tier.SUPPRESSED, Tier.MUST_REVIEW)


def test_flags_verify_and_score_against_a_frame_range_label() -> None:
    tl = timeline({(1, 0): TEXT})
    check = ClrPhone(hits=[hit("clr.phone", TEXT, 1)], registry=LOG, keyframes=KFS, cfg=CFG)
    flags = run_check(check, tl, "run_1", PB)
    kept, dropped = verify(flags, tl, [check])
    assert len(kept) == 1 and not dropped
    f = kept[0]
    assert f.verification.evidence == "pass" and f.verification.rule_recheck == "pass"
    kf = next(e for e in f.evidence if e.kind is EvidenceKind.KEYFRAME)
    assert kf.quote == TEXT and kf.crop and kf.crop.box == [0.3, 0.4, 0.2, 0.1]
    label = Label(
        label_id="t-clr-1", title="t", episode="S01E01", check="clr.phone",
        target=Target(kind="frame_range", frames=(100, 150)),
        description="x", injector="clr.text.v1", seed=1,
    )  # fmt: skip
    assert match(kept, [label]) == [(0, 0)]  # the keyframe's cell [96, 192) overlaps it by 50/96


def test_a_quote_the_keyframe_text_lacks_is_left_out_not_invented() -> None:
    tl = timeline({})  # the keyframe span carries no OCR text
    (f,) = flags_of([hit("clr.phone", TEXT, 0)], tl)
    kf = next(e for e in f.evidence if e.kind is EvidenceKind.KEYFRAME)
    assert kf.quote is None


def test_recheck_follows_the_stored_detections() -> None:
    tl = timeline({(0, 0): TEXT})
    check = ClrPhone(hits=[hit("clr.phone", TEXT, 0)], registry=LOG, keyframes=KFS, cfg=CFG)
    (flag,) = run_check(check, tl, "run_1", PB)
    assert check.recheck(flag, tl)
    gone = ClrPhone(hits=[], registry=LOG, keyframes=KFS, cfg=CFG)
    assert not gone.recheck(flag, tl)
    relogged = ClrPhone(
        hits=[hit("clr.phone", TEXT, 0)], registry=Registry(), keyframes=KFS, cfg=CFG
    )
    assert not relogged.recheck(flag, tl)  # no longer matches the logged item


def test_file_mode_has_no_store_and_no_findings() -> None:
    assert ClrPhone().units(timeline({})) == []


def test_work_unit_keys_are_stable() -> None:
    tl = timeline({(0, 0): TEXT})
    a, b = (
        ClrPhone(hits=[hit("clr.phone", TEXT, 0)], registry=LOG, keyframes=KFS, cfg=CFG)
        for _ in range(2)
    )
    assert (
        [u.key for u in a.units(tl)]
        == [u.key for u in b.units(tl)]
        == ["S01E01/clr.phone/clr/1/f0"]
    )


def rows(include_hidden: bool = False) -> tuple[list[dict[str, Any]], Timeline]:
    tl = timeline({})
    hits = [
        hit("clr.phone", TEXT, 0, detection_id=11),
        hit("clr.phone", "(415) 555-2671", 1, detection_id=12),
        hit("clr.plate", "7KLM482", 2, detection_id=13),
        hit("clr.phone", "(617) 482-9154", 2, detection_id=14),
    ]
    occs = analyze(hits, LOG, tl, CFG, KFS)
    ids = {refs.keyframe("S01E01", 0, 0): "flg_5"}
    return occurrence_rows(occs, tl, "show", ids, include_hidden=include_hidden), tl


def test_csv_has_the_documented_columns_and_hides_cleared() -> None:
    assert COLUMNS == [
        "occurrence_id", "item", "kind", "status", "tc_in", "tc_out", "screen_time_s",
        "prominence", "severity", "thumbnail_url", "flag_id",
    ]  # fmt: skip
    r, _ = rows()
    assert [x["status"] for x in r] == ["pending", "unknown", "denied"]  # cleared is hidden
    first = r[0]
    assert first["occurrence_id"] == "occ_1" and first["item"] == TEXT and first["kind"] == "phone"
    assert first["flag_id"] == "flg_5" and first["tc_in"] == "00:00:00:00"
    assert first["thumbnail_url"].endswith("/show/S01E01/crops/11.jpg")
    assert float(first["screen_time_s"]) == 4.0 and first["prominence"] in (
        "featured",
        "background",
    )
    assert r[1]["item"] == "(617) 482-9154" and r[1]["flag_id"] == ""  # not in the log
    hidden, _ = rows(include_hidden=True)
    assert [x["status"] for x in hidden] == ["pending", "cleared", "unknown", "denied"]


def test_csv_round_trips() -> None:
    r, _ = rows(include_hidden=True)
    text = to_csv(r)
    assert text.splitlines()[0] == ",".join(COLUMNS)
    back = from_csv(text)
    assert back == [{k: str(v) for k, v in row.items()} for row in r]
    assert len(back) == 4
