import pytest

from nip.agents.base import run_check
from nip.agents.localization.readability import Readability
from nip.contracts.flag import CheckId, EvidenceKind, Flag, ProducedBy
from nip.contracts.timeline import Span, Timeline
from nip.verification.verify import verify

PB = ProducedBy(model_variant=None, plan_id="plan_1")


def _tl(text: str = "Hola.", frames: tuple[int, int] = (0, 10), duration: int = 1000) -> Timeline:
    cue = Span(kind=EvidenceKind.SUBTITLE_CUE, ref="E1/es/1", frames=frames, lang="es", text=text)
    return Timeline(episode="E1", fps=(24, 1), duration_frames=duration, spans=[cue])


@pytest.fixture
def flag() -> Flag:
    (f,) = run_check(Readability(["es"]), _tl(), "run_1", PB)  # 10 frames: too short
    return f


def test_resolving_flag_passes_both_steps(flag: Flag) -> None:
    kept, dropped = verify([flag], _tl(), {CheckId.LOC_READABILITY: Readability(["es"]).recheck})
    assert dropped == []
    assert (kept[0].verification.evidence, kept[0].verification.rule_recheck) == ("pass", "pass")


def test_no_recheck_registered_is_na(flag: Flag) -> None:
    (kept,), _ = verify([flag], _tl(), {})
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
    kept, dropped = verify([flag], tl, {})
    assert kept == [] and reason in dropped[0][1]
    assert dropped[0][0].verification.evidence == "fail"


def test_stale_rule_result_is_dropped(flag: Flag) -> None:
    def never(f: Flag, tl: Timeline) -> bool:
        return False

    kept, dropped = verify([flag], _tl(), {CheckId.LOC_READABILITY: never})
    assert kept == [] and "re-check" in dropped[0][1]
    assert dropped[0][0].verification.rule_recheck == "fail"
