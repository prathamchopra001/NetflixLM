import pytest

from nip.agents.base import Check, run_check
from nip.agents.localization.readability import Readability
from nip.contracts.flag import EvidenceKind, Flag, ProducedBy
from nip.contracts.timeline import Span, Timeline
from nip.verification.verify import verify

PB = ProducedBy(model_variant=None, plan_id="plan_1")


def _tl(text: str = "Hola.", frames: tuple[int, int] = (0, 10), duration: int = 1000) -> Timeline:
    cue = Span(kind=EvidenceKind.SUBTITLE_CUE, ref="E1/es/1", frames=frames, lang="es", text=text)
    return Timeline(episode="E1", fps=(24, 1), duration_frames=duration, spans=[cue])


class NoRecheck(Readability):
    """A rule check whose author forgot `recheck`: it keeps the base class's (None)."""

    recheck = Check.recheck


class Stale(Readability):
    def recheck(self, flag: Flag, tl: Timeline) -> bool | None:
        return False


class Judged(Readability):
    """An LLM-style check: not rule-originated, so step 2 does not apply."""

    rule_originated = False

    def recheck(self, flag: Flag, tl: Timeline) -> bool | None:
        raise AssertionError("step 2 must not run")


@pytest.fixture
def flag() -> Flag:
    (f,) = run_check(Readability(["es"]), _tl(), "run_1", PB)  # 10 frames: too short
    return f


def test_resolving_flag_passes_both_steps(flag: Flag) -> None:
    kept, dropped = verify([flag], _tl(), [Readability(["es"])])
    assert dropped == []
    assert (kept[0].verification.evidence, kept[0].verification.rule_recheck) == ("pass", "pass")


@pytest.mark.parametrize(
    ("checks", "reason"),
    [
        ([], "no loc.readability check was given"),
        ([NoRecheck(["es"])], "has no rule re-check"),
        ([Stale(["es"])], "no longer reproduces"),
    ],
)
def test_rule_recheck_fails_closed(flag: Flag, checks: list[Readability], reason: str) -> None:
    kept, dropped = verify([flag], _tl(), checks)
    assert kept == [] and reason in dropped[0][1]
    assert dropped[0][0].verification.rule_recheck == "fail"


def test_non_rule_check_skips_the_recheck(flag: Flag) -> None:
    (kept,), _ = verify([flag], _tl(), [Judged(["es"])])
    assert kept.verification.rule_recheck == "n/a"


@pytest.mark.parametrize(
    ("tl", "reason"),
    [
        (Timeline(episode="E1", fps=(24, 1), duration_frames=1000, spans=[]), "does not resolve"),
        (_tl(text="Adiós."), "quote does not match"),
        (_tl(frames=(0, 11)), "differ from the timeline"),
        (_tl(duration=5), "outside the episode"),
    ],
)
def test_evidence_resolver_drops(flag: Flag, tl: Timeline, reason: str) -> None:
    kept, dropped = verify([flag], tl, [Readability(["es"])])
    assert kept == [] and reason in dropped[0][1]
    assert dropped[0][0].verification.evidence == "fail"
