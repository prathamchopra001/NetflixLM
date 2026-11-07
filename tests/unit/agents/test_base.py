import logging
from fractions import Fraction

import pytest

from nip.agents.base import (
    Check,
    Finding,
    Input,
    WorkUnit,
    cue_windows,
    emit,
    run_check,
    tier_for,
)
from nip.agents.localization.readability import Readability, rule_pack
from nip.contracts.flag import (
    Agent,
    Category,
    CheckId,
    Evidence,
    EvidenceKind,
    EvidenceRole,
    ProducedBy,
    Tier,
)
from nip.contracts.timeline import Span, Timeline
from nip.ingest import parse_srt
from nip.ingest.media import MediaInfo
from nip.ingest.script import Element, Scene, Script
from nip.timeline.estimate import build_timeline

PB = ProducedBy(model_variant=None, plan_id="plan_1")
SRT = "".join(
    f"{i}\n00:00:{i:02d},000 --> 00:00:{i:02d},500\ncue {i}\n\n" for i in range(1, 46)
)  # 45 cues


@pytest.fixture
def tl() -> Timeline:
    script = Script(None, [Scene("12", "INT. ROOM - DAY", [Element("action", "x")])])
    subs = parse_srt(SRT).data
    assert subs
    return build_timeline("S01E03", script, subtitles={"es-419": subs})


def _cue_ev(ref: str, role: EvidenceRole = EvidenceRole.CLAIM) -> Evidence:
    return Evidence(kind=EvidenceKind.SUBTITLE_CUE, ref=ref, role=role, quote="cue 2")


class LongCues(Check):
    """Toy check: flags every cue whose text ends in '2'."""

    check = CheckId.LOC_READABILITY
    requires = frozenset({Input.SOURCE_SUBS, Input.TARGET_SUBS})

    def units(self, tl: Timeline) -> list[WorkUnit]:
        return cue_windows(tl, "es-419")

    def run(self, unit: WorkUnit, tl: Timeline) -> list[Finding]:
        return [
            Finding(4, 0.95, "ends in 2", "x", [_cue_ev(c.ref)], lang="es-419")
            for c in unit.spans
            if c.text.endswith("2")
        ]


def test_active_needs_every_required_input() -> None:
    assert LongCues.active({Input.SCRIPT, Input.SOURCE_SUBS, Input.TARGET_SUBS})
    assert not LongCues.active([Input.TARGET_SUBS, Input.PICTURE])


def test_cue_windows(tl: Timeline) -> None:
    units = cue_windows(tl, "es-419")
    assert [u.key for u in units] == [
        "S01E03/es-419/1-20",
        "S01E03/es-419/21-40",
        "S01E03/es-419/41-45",
    ]
    assert [len(u.spans) for u in units] == [20, 20, 5]
    assert units[1].spans[0].ref == "S01E03/es-419/21"
    assert cue_windows(tl, "fr-FR") == []


@pytest.mark.parametrize(
    ("conf", "tier"),
    [(0.9, Tier.MUST_REVIEW), (0.89, Tier.REVIEW_RECOMMENDED), (0.7, Tier.REVIEW_RECOMMENDED),
     (0.69, Tier.SUPPRESSED)],
)  # fmt: skip
def test_tier_for(conf: float, tier: Tier) -> None:
    assert tier_for(conf) is tier


def test_tier_thresholds_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NIP_TIER_MUST_REVIEW", "0.8")
    assert tier_for(0.85) is Tier.MUST_REVIEW


def test_emit_resolves_evidence_to_timeline_spans(tl: Timeline) -> None:
    finding = Finding(
        3, 0.75, "t", "e", [_cue_ev("S01E03/es-419/2"),
                            Evidence(kind=EvidenceKind.SCENE, ref="S01E03/sc/12", role="context")],
    )  # fmt: skip
    flag = emit(finding, CheckId.LOC_READABILITY, tl, "run_1", PB)
    assert flag is not None
    assert (flag.agent, flag.category) == (Agent.LOCALIZATION_AUDITOR, Category.LOCALIZATION)
    assert flag.tier is Tier.REVIEW_RECOMMENDED and flag.episode == "S01E03"
    cue, scene = flag.evidence
    assert cue.frames == tl.resolve("S01E03/es-419/2").frames == (48, 60)  # type: ignore[union-attr]
    assert (cue.tc_in, cue.tc_out, cue.lang, cue.scene) == (
        "00:00:02:00",
        "00:00:02:12",
        "es-419",
        None,
    )
    assert cue.quote == "cue 2"  # the check's own fields are kept
    assert scene.scene == "S01E03 · Sc 12 (script estimate)" and scene.tc_in is None
    assert scene.frames == tl.resolve("S01E03/sc/12").frames  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "ev",
    [
        _cue_ev("S01E03/es-419/99"),  # no such cue
        _cue_ev("S01E04/es-419/2"),  # other episode
        Evidence(kind=EvidenceKind.SHOT, ref="S01E03/es-419/2", role="claim"),  # wrong kind
        Evidence(kind=EvidenceKind.FACT, ref="fact/1", role="claim"),  # not a timeline object
    ],
)
def test_emit_drops_unresolvable_evidence(
    tl: Timeline, ev: Evidence, caplog: pytest.LogCaptureFixture
) -> None:
    finding = Finding(3, 0.95, "t", "e", [_cue_ev("S01E03/es-419/1"), ev])
    with caplog.at_level(logging.WARNING):
        assert emit(finding, CheckId.LOC_READABILITY, tl, "run_1", PB) is None
    assert ev.ref in caplog.text


def test_run_check_emits_one_flag_per_finding(tl: Timeline) -> None:
    flags = run_check(LongCues(), tl, "run_1", PB)
    assert [f.evidence[0].ref for f in flags] == [f"S01E03/es-419/{i}" for i in (2, 12, 22, 32, 42)]
    assert all(f.check is CheckId.LOC_READABILITY and f.lang == "es-419" for f in flags)
    assert all(f.evidence[0].frames is not None for f in flags)


def test_frames_follow_the_timeline_rate() -> None:
    subs = parse_srt("1\n00:00:01,000 --> 00:00:02,000\nx\n").data
    assert subs
    script = Script(None, [Scene("1", "INT. A - DAY")])

    media = MediaInfo("v", Fraction(25), 1000, 1, 1, "h264", "yuv420p", 0, False, 0)
    tl = build_timeline("E1", script, media, {"en": subs})
    flag = emit(
        Finding(2, 0.5, "t", "e", [_cue_ev("E1/en/1")]), CheckId.LOC_READABILITY, tl, "r", PB
    )
    assert flag and flag.evidence[0].frames == (25, 50) and flag.tier is Tier.SUPPRESSED


def test_cue_windows_carry_the_cue_before_as_context(tl: Timeline) -> None:
    units = cue_windows(tl, "es-419")
    assert [[c.ref for c in u.context] for u in units] == [
        [],
        ["S01E03/es-419/20"],
        ["S01E03/es-419/40"],
    ]


# Every Check class, with a timeline it flags on. New checks add themselves here.
CHECKS: list[tuple[Check, str]] = [(Readability(["es"]), "es")]


@pytest.mark.parametrize(("check", "lang"), CHECKS, ids=lambda c: str(getattr(c, "check", c)))
def test_a_unit_lists_everything_its_check_reads(check: Check, lang: str) -> None:
    """Lint for stage-cache keys: run on a timeline holding only the unit's spans + context, a
    check finds exactly what it finds on the whole timeline."""
    cues = [  # 1-frame gaps everywhere: every cue's verdict depends on the cue before it
        Span(kind=EvidenceKind.SUBTITLE_CUE, ref=f"E1/{lang}/{i}", frames=(50 * i, 50 * i + 49),
             lang=lang, text="Hola.")
        for i in range(1, 46)
    ]  # fmt: skip
    tl = Timeline(episode="E1", fps=(24, 1), duration_frames=10_000, spans=cues)
    units = check.units(tl)
    assert len(units) > 1
    for unit in units:
        alone = tl.model_copy(update={"spans": unit.context + unit.spans})
        assert check.run(unit, alone) == check.run(unit, tl) != []


def test_readability_cache_inputs() -> None:
    check = Readability(["es"], audience="children")
    assert check.version and check.params() == {
        "audience": "children",
        "rules": {"es": rule_pack("es")["readability"]},
    }
