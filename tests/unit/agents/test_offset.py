"""loc.offset (2.4): a target track shifted by a constant, at 24/1 and 24000/1001."""

from fractions import Fraction

import pytest

from nip.agents.base import Input, run_check
from nip.agents.localization import CHECKS
from nip.agents.localization.drift import Drift, Offset
from nip.contracts.flag import EvidenceRole, Flag, ProducedBy, Tier
from nip.contracts.timeline import Timeline
from tests.unit.agents.test_drift import N24, NTSC, tl

PB = ProducedBy(model_variant=None, plan_id="plan_1")


def flags(t: Timeline) -> list[Flag]:
    return run_check(Offset(["es"], "en"), t, "run_1", PB)


@pytest.mark.parametrize("fps", [N24, NTSC])
@pytest.mark.parametrize("merge", [False, True])
@pytest.mark.parametrize("frames", [-24, -12, 12, 24, 36])
def test_planted_offset_is_flagged_in_frames_of_the_probed_rate(
    fps: Fraction, merge: bool, frames: int
) -> None:
    (flag,) = flags(tl(fps, shift=float(frames / fps), merge=merge))
    assert (flag.check, flag.lang, flag.tier) == ("loc.offset", "es", Tier.MUST_REVIEW)
    assert f"{frames:+d} frames" in flag.title
    assert flag.suggested_fix == f"Shift every cue by {-frames:+d} frames."
    claims = [e for e in flag.evidence if e.role is EvidenceRole.CLAIM]
    assert claims[0].ref == "E1/es/1" and len(claims) == 2  # R12: first and last cue


def test_same_seconds_are_different_frames_at_different_rates() -> None:
    assert "+12 frames" in flags(tl(N24, shift=0.5))[0].title
    assert "+12 frames" in flags(tl(NTSC, shift=0.5))[0].title  # 11.99 frames, rounded
    assert "+24 frames" in flags(tl(N24, shift=1.0))[0].title
    assert "+24 frames" in flags(tl(NTSC, shift=1.001))[0].title  # 1.001 s is 24 frames at 23.976


@pytest.mark.parametrize("fps", [N24, NTSC])
def test_small_offsets_and_clean_tracks_are_not_flagged(fps: Fraction) -> None:
    assert flags(tl(fps)) == []
    assert flags(tl(fps, shift=0.2)) == []  # under offset_min_s (6 frames at 24)
    assert flags(tl(fps, shift=-0.2, merge=True)) == []


def test_offset_with_drift_reports_the_constant_term_only() -> None:
    t = tl(N24, ratio=25 / 24, shift=1.0)
    assert [f.check for f in run_check(Drift(["es"], "en"), t, "run_1", PB)] == ["loc.drift"]
    (flag,) = flags(t)
    assert "+24 frames" in flag.title  # the intercept, not a median that the drift pushed away


def test_recheck_and_inputs() -> None:
    check = Offset(["es"], "en")
    t = tl(N24, shift=0.5)
    (flag,) = run_check(check, t, "run_1", PB)
    assert check.recheck(flag, t) is True
    assert check.recheck(flag, tl(N24)) is False
    assert Offset in CHECKS
    assert Offset.active({Input.SOURCE_SUBS, Input.TARGET_SUBS})  # the picture is optional
    assert not Offset.active({Input.SOURCE_SUBS})


@pytest.mark.parametrize("shift", [-1.0, -0.5, 0.5, 1.0])
@pytest.mark.parametrize("merge", [False, True])
def test_offset_without_a_picture_is_stated_in_seconds_only(shift: float, merge: bool) -> None:
    (flag,) = flags(tl(N24, shift=shift, merge=merge, picture=False))
    assert flag.title == f"Track is {shift:+.3f} s off the source"
    assert (
        "frames" not in flag.title and flag.suggested_fix == f"Shift every cue by {-shift:+.3f} s."
    )
    assert flags(tl(N24, shift=0.2, picture=False)) == []
