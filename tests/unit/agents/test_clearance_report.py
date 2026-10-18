"""Clearance flags and report: routing per status (pending/denied never hidden, even misread),
evidence that verifies and scores against a frame-range label, the occurrence refs, the CSV."""

from fractions import Fraction
from typing import Any

import pytest

from eval.injectors.base import Label, Target
from eval.metrics import SHOWN, match
from nip.agents.base import Input, run_check
from nip.agents.clearance import CHECKS, ClrPhone
from nip.agents.clearance.checks import (
    ClearanceText,
    ClrAddress,
    ClrBrandText,
    ClrPlate,
    ClrUrl,
)
from nip.agents.clearance.matching import Item, Registry
from nip.agents.clearance.occurrences import Hit, Occurrence, analyze
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


def hit(check: str, text: str, shot: int, conf: float = 0.95, **kw: Any) -> Hit:
    return Hit(check, text, shot, 0, (0.3, 0.4, 0.2, 0.1), conf, "pp-ocrv6-medium", 300.0, **kw)


def build(
    hits: list[Hit], registry: Registry = LOG, ocr_text: bool = True
) -> tuple[Timeline, list[Occurrence]]:
    """Shots [0, 96), [96, 192), [192, 288) at 24 fps, one keyframe each, the clearance items as
    `clr/{id}` spans; then what the OCR stage does: the keyframes get their text and every
    occurrence its `clr/occ-...` span."""
    fps = Fraction(24)
    shots = [(0, 96), (96, 192), (192, 288)]
    spans = [
        Span(kind=EvidenceKind.SHOT, ref=refs.shot("S01E01", i), frames=s,
             tc_in=frame_to_smpte(s[0], fps), tc_out=frame_to_smpte(s[1], fps))
        for i, s in enumerate(shots)
    ]  # fmt: skip
    for i, n, f in KFS:
        spans.append(
            Span(kind=EvidenceKind.KEYFRAME, ref=refs.keyframe("S01E01", i, n), frames=(f, f + 1),
                 tc_in=frame_to_smpte(f, fps), tc_out=frame_to_smpte(f + 1, fps))
        )  # fmt: skip
    spans += [
        Span(kind=EvidenceKind.CLEARANCE_ITEM, ref=f"clr/{i.id}", text=i.name)
        for i in registry.items
    ]
    tl = Timeline(episode="S01E01", fps=(24, 1), duration_frames=288, spans=tuple(spans))
    scans: dict[tuple[int, int], Scan] = {}
    for h in hits if ocr_text else []:
        line = Detection(h.shot, h.n, h.text, h.box, 0.9, "pp-ocrv6-medium")
        scans.setdefault((h.shot, h.n), Scan([], [], [])).lines.append(line)
    occs = analyze(hits, registry, tl, CFG, KFS)
    return with_ocr(tl, scans, occs), occs


def test_with_ocr_replaces_the_spans_of_an_earlier_scan() -> None:
    """`load_timeline` hands the stage a timeline that already has the stored occurrences."""
    hits = [hit("clr.phone", TEXT, 0)]
    tl, occs = build(hits)
    again = with_ocr(tl, {}, occs)
    assert [s.ref for s in again.spans if refs.is_occurrence(s.ref)] == [o.ref for o in occs]
    assert with_ocr(tl, {}, []).resolve(occs[0].ref) is None
    assert with_ocr(tl, {}, []).resolve(refs.keyframe("S01E01", 0, 0)).text == TEXT  # type: ignore[union-attr]


def flags_of(
    hits: list[Hit], check: type[ClearanceText] = ClrPhone, registry: Registry = LOG,
    ocr_text: bool = True,
) -> list[Flag]:  # fmt: skip
    tl, _ = build(hits, registry, ocr_text)
    c = check(hits=hits, registry=registry, keyframes=KFS, cfg=CFG)
    return run_check(c, tl, "run_1", PB)


def kf_ref(flag: Flag) -> str:
    return next(e.ref for e in flag.evidence if e.kind is EvidenceKind.KEYFRAME)


def test_checks_list_and_activation() -> None:
    assert [str(c.check) for c in CHECKS] == [
        "clr.phone", "clr.url", "clr.email", "clr.address", "clr.plate", "clr.brand_text",
    ]  # fmt: skip
    assert all(c.active({Input.PICTURE}) and not c.active({Input.SCRIPT}) for c in CHECKS)


def test_each_status_routes_as_the_architecture_says() -> None:
    hits = [
        hit("clr.phone", TEXT, 0),
        hit("clr.phone", "(415) 555-2671", 1),
        hit("clr.phone", "(617) 482-9154", 2),
    ]
    got = {kf_ref(f): f for f in flags_of(hits)}
    pending, cleared, unknown = (got[refs.keyframe("S01E01", i, 0)] for i in range(3))
    assert (pending.tier, pending.severity) == (Tier.MUST_REVIEW, CFG["severity"]["pending"])
    assert cleared.tier is Tier.SUPPRESSED and cleared.suggested_fix is None  # kept for the audit
    assert unknown.tier is Tier.MUST_REVIEW and unknown.severity == CFG["severity"]["featured"]
    assert "not in the clearance log" in unknown.explanation
    assert any(e.ref == "clr/1" and e.role is EvidenceRole.CONTEXT for e in pending.evidence)
    assert not any(e.ref == "clr/1" for e in unknown.evidence)  # an unknown item cites no item
    # a fictional name is not a clearance item: no flag at all
    assert not flags_of([hit("clr.brand_text", "KAPPA COLA", 0)], ClrBrandText)


@pytest.mark.parametrize("confidence", [0.0, 0.01, 0.3, 0.69, 0.7, 0.95, 1.0])
@pytest.mark.parametrize(("check", "text"), [
    ("clr.phone", TEXT),
    ("clr.plate", "7KLM482"),
    ("clr.plate", "7KLM462"),  # one OCR misread of the denied plate
    ("clr.phone", "(212) 555-0284"),  # one digit off the pending number
    ("clr.plate", "7KIM482"),  # I for L
])  # fmt: skip
def test_pending_and_denied_are_never_hidden_not_even_when_misread(
    check: str, text: str, confidence: float
) -> None:
    cls = next(c for c in CHECKS if str(c.check) == check)
    (flag,) = flags_of([hit(check, text, 0, confidence)], cls)
    assert flag.tier is Tier.MUST_REVIEW and flag.tier in SHOWN
    assert flag.severity >= 4 and flag.confidence == confidence
    assert any(
        e.kind is EvidenceKind.CLEARANCE_ITEM
        and e.ref in ("clr/1", "clr/3")
        and e.role is EvidenceRole.CONTEXT
        for e in flag.evidence
    )
    if text not in (TEXT, "7KLM482"):
        assert "may be the" in flag.explanation and "one character" in flag.explanation


def test_two_edits_or_a_cleared_neighbour_stay_unknown() -> None:
    far = flags_of([hit("clr.plate", "7KLX4X2", 0, 0.3)], ClrPlate)
    assert far[0].tier is Tier.SUPPRESSED and "not in the clearance log" in far[0].explanation
    # a number one digit off a CLEARED one is not that item: exact matching stays for cleared
    off = flags_of([hit("clr.phone", "(415) 555-2672", 0, 0.3)])
    assert off[0].tier is Tier.SUPPRESSED and "not in the clearance log" in off[0].explanation


def test_an_unknown_item_is_routed_by_confidence() -> None:
    low, high = (flags_of([hit("clr.phone", "(617) 482-9154", 0, c)])[0].tier for c in (0.5, 0.95))
    assert (low, high) == (Tier.SUPPRESSED, Tier.MUST_REVIEW)


def test_flags_verify_and_the_claim_is_the_occurrence_range_the_csv_reports() -> None:
    hits = [hit("clr.phone", TEXT, 1)]
    tl, occs = build(hits)
    check = ClrPhone(hits=hits, registry=LOG, keyframes=KFS, cfg=CFG)
    flags = run_check(check, tl, "run_1", PB)
    kept, dropped = verify(flags, tl, [check])
    assert len(kept) == 1 and not dropped
    f = kept[0]
    assert f.verification.evidence == "pass" and f.verification.rule_recheck == "pass"
    claim = next(e for e in f.evidence if e.role is EvidenceRole.CLAIM)
    assert claim.ref == occs[0].ref and claim.frames == occs[0].frames == (96, 192)
    rows_ = occurrence_rows(occs, tl, "show", {})
    assert (claim.tc_in, claim.tc_out) == (rows_[0]["tc_in"], rows_[0]["tc_out"])
    kf = next(e for e in f.evidence if e.kind is EvidenceKind.KEYFRAME)
    assert kf.quote == TEXT and kf.crop and kf.crop.box == [0.3, 0.4, 0.2, 0.1]
    assert kf.role is EvidenceRole.CONTEXT and kf.frames == (144, 145)  # as stored
    label = Label(
        label_id="t-clr-1", title="t", episode="S01E01", check="clr.phone",
        target=Target(kind="frame_range", frames=(100, 150)),
        description="x", injector="clr.text.v1", seed=1,
    )  # fmt: skip
    assert match(kept, [label]) == [(0, 0)]  # [96, 192) against [100, 150): IoU 50/96


def test_a_label_much_longer_than_the_occurrence_does_not_match_and_is_not_tuned_for() -> None:
    """The claim is the occurrence's range. A sign shown for 60 s but seen at one keyframe has a
    4 s occurrence, so its 60 s label has IoU 0.07: reported, not hidden by widening the claim."""
    hits = [hit("clr.phone", TEXT, 1)]
    tl, _ = build(hits)
    check = ClrPhone(hits=hits, registry=LOG, keyframes=KFS, cfg=CFG)
    flags = run_check(check, tl, "run_1", PB)
    label = Label(
        label_id="t-clr-2", title="t", episode="S01E01", check="clr.phone",
        target=Target(kind="frame_range", frames=(0, 1440)),
        description="x", injector="clr.text.v1", seed=1,
    )  # fmt: skip
    assert match(flags, [label]) == []


def test_a_quote_the_keyframe_text_lacks_is_left_out_not_invented() -> None:
    (f,) = flags_of([hit("clr.phone", TEXT, 0)], ocr_text=False)
    kf = next(e for e in f.evidence if e.kind is EvidenceKind.KEYFRAME)
    assert kf.quote is None


def test_recheck_follows_the_stored_detections() -> None:
    hits = [hit("clr.phone", TEXT, 0)]
    tl, _ = build(hits)
    check = ClrPhone(hits=hits, registry=LOG, keyframes=KFS, cfg=CFG)
    (flag,) = run_check(check, tl, "run_1", PB)
    assert check.recheck(flag, tl)
    gone = ClrPhone(hits=[], registry=LOG, keyframes=KFS, cfg=CFG)
    assert not gone.recheck(flag, tl)
    relogged = ClrPhone(hits=hits, registry=Registry(), keyframes=KFS, cfg=CFG)
    assert not relogged.recheck(flag, tl)  # no longer matches the logged item


def test_file_mode_has_no_store_and_no_findings() -> None:
    assert ClrPhone().units(build([])[0]) == []


def test_work_unit_keys_are_stable() -> None:
    hits = [hit("clr.phone", TEXT, 0)]
    tl, _ = build(hits)
    a, b = (ClrPhone(hits=hits, registry=LOG, keyframes=KFS, cfg=CFG) for _ in range(2))
    keys = [u.key for u in a.units(tl)]
    assert keys == [u.key for u in b.units(tl)] == ["S01E01/clr.phone/clr/1/f0"]


def test_distinct_unknown_items_never_share_a_fingerprint() -> None:
    """R13: the fingerprint is check + stable refs. Before the occurrence ref every unknown item
    on one keyframe had one identity (41 of 109 flags on the benchmark collided)."""
    from nip.store.runs import fingerprint

    hits = [
        hit("clr.url", "orange.blender.org", 0),
        hit("clr.url", "peach.blender.org", 0),  # same keyframe, another item
        hit("clr.url", "orange.blender.org", 2),  # the first item again, later: its own occurrence
    ]
    flags = flags_of(hits, ClrUrl)
    assert len(flags) == 3 and len({fingerprint(f) for f in flags}) == 3
    again = flags_of(hits, ClrUrl)  # a re-run reproduces them
    assert [fingerprint(f) for f in flags] == [fingerprint(f) for f in again]


def rows(include_hidden: bool = False) -> tuple[list[dict[str, Any]], Timeline]:
    hits = [
        hit("clr.phone", TEXT, 0, detection_id=11),
        hit("clr.phone", "(415) 555-2671", 1, detection_id=12),
        hit("clr.plate", "7KLM482", 2, detection_id=13),
        hit("clr.phone", "(617) 482-9154", 2, detection_id=14),
    ]
    tl, occs = build(hits)
    ids = {("clr.phone", refs.keyframe("S01E01", 0, 0), None): "flg_5"}
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
    assert float(first["screen_time_s"]) == 4.0
    assert first["prominence"] in ("featured", "background")
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


def test_logged_items_with_the_films_own_words_still_flag_and_get_a_csv_row() -> None:
    """N1: a pending / denied item containing the show title, a one-word bible name or credit
    words is must_review and in the CSV (the junk rules never ran before the log)."""
    reg = Registry(
        (
            Item(1, "Waffle House", "brand", "denied"),
            Item(2, "12 Springfield Road", "address", "pending"),
            Item(3, "Sound Design", "brand", "pending"),
        ),
        fictional=("House", "Springfield"),
    )
    hits = [
        hit("clr.brand_text", "WAFFLE HOUSE", 0, 0.2),
        hit("clr.address", "12 Springfield Road", 1, 0.2),
        hit("clr.brand_text", "Sound Design", 2, 0.2),
    ]
    tl, occs = build(hits, reg)
    flags = flags_of(hits, ClrBrandText, reg) + flags_of(hits, ClrAddress, reg)
    assert len(flags) == 3 and all(f.tier is Tier.MUST_REVIEW for f in flags)
    csv_rows = occurrence_rows(occs, tl, "show", {})
    assert [(r["item"], r["status"]) for r in csv_rows] == [
        ("Waffle House", "denied"),
        ("12 Springfield Road", "pending"),
        ("Sound Design", "pending"),
    ]
