"""loc.drift (2.4): a target track timed for another frame rate, at 24/1 and 24000/1001.
Offsets are in test_offset.py."""

import random
from fractions import Fraction

import pytest

from nip.agents.base import Input, run_check
from nip.agents.localization import CHECKS
from nip.agents.localization.drift import Drift, Offset, confusions
from nip.contracts.flag import EvidenceKind, EvidenceRole, Flag, ProducedBy, Tier
from nip.contracts.timeline import Span, Timeline

PB = ProducedBy(model_variant=None, plan_id="plan_1")
N24, NTSC = Fraction(24), Fraction(24000, 1001)


def source(n: int = 150, seed: int = 5) -> list[tuple[float, float]]:
    rng, out, t = random.Random(seed), [], 2.0
    for _ in range(n):
        d = rng.uniform(1.2, 3.0)
        out.append((t, t + d))
        t += d + rng.uniform(0.9, 3.5)
    return out


def tl(fps: Fraction, ratio: float = 1.0, shift: float = 0.0, merge: bool = False) -> Timeline:
    """en = `source()`; es = the same cues moved to ratio * t + shift (every 6th pair merged)."""
    src = source()
    tgt = []
    i = 0
    while i < len(src):
        a, b = src[i]
        if merge and i % 6 == 0 and i + 1 < len(src):
            b, i = src[i + 1][1], i + 1
        tgt.append((a, b))
        i += 1
    spans = []
    for lang, cues, r, s in (("en", src, 1.0, 0.0), ("es", tgt, ratio, shift)):
        for k, (a, b) in enumerate(cues, 1):
            f = (round((r * a + s) * fps), round((r * b + s) * fps))
            ref = f"E1/{lang}/{k}"
            spans.append(
                Span(kind=EvidenceKind.SUBTITLE_CUE, ref=ref, frames=f, lang=lang, text=ref)
            )
    return Timeline(
        episode="E1", fps=(fps.numerator, fps.denominator), duration_frames=10**6, spans=spans
    )


def flags(t: Timeline) -> list[Flag]:
    return run_check(Drift(["es"], "en"), t, "run_1", PB)


@pytest.mark.parametrize("fps", [N24, NTSC])
@pytest.mark.parametrize("merge", [False, True])
def test_clean_track_is_not_flagged(fps: Fraction, merge: bool) -> None:
    assert flags(tl(fps, shift=0.05, merge=merge)) == []


@pytest.mark.parametrize(
    ("fps", "ratio", "cause"),
    [
        (N24, 25 / 24, "timing for a 25 fps picture"),  # 25 fps timing on a 24/1 picture: 4.17%
        (N24, 1000 / 1001, "timing for a 23.976 fps picture"),  # media time vs 24: -0.1%
        (NTSC, 25025 / 24000, "timing for a 25 fps picture"),  # 4.27% on 24000/1001
        (NTSC, 1001 / 1000, "timing for a 24 fps picture"),  # SMPTE-24 vs 23.976 media time: 0.1%
        (NTSC, 24000 / 25025, "of a 25 fps picture read as 23.976"),  # and the other direction
    ],
)
@pytest.mark.parametrize("merge", [False, True])
def test_planted_drift_is_flagged_and_classified(
    fps: Fraction, ratio: float, cause: str, merge: bool
) -> None:
    (flag,) = flags(tl(fps, ratio=ratio, merge=merge))
    assert (flag.check, flag.lang, flag.tier, flag.confidence) == (
        "loc.drift",
        "es",
        Tier.MUST_REVIEW,
        0.99,
    )
    assert cause in flag.explanation
    # R12: the claims are the first and the last cue of the track
    claims = [e for e in flag.evidence if e.role is EvidenceRole.CLAIM]
    n = len(tl(fps, merge=merge).of(EvidenceKind.SUBTITLE_CUE, "es"))
    assert [e.ref for e in claims] == ["E1/es/1", f"E1/es/{n}"]


def test_unknown_slope_is_flagged_less_confidently() -> None:
    (flag,) = flags(tl(N24, ratio=1.02))  # matches no confusion of the rule pack
    assert flag.confidence == 0.9 and "no known frame-rate confusion" in flag.explanation


def test_slope_below_the_threshold_is_not_drift() -> None:
    assert flags(tl(N24, ratio=1.0003)) == []  # 0.03%: under drift_min_slope


def test_pure_rescale_has_no_offset() -> None:
    """A rescale about 0 has no constant term: only the drift check fires."""
    t = tl(N24, ratio=25 / 24)
    assert run_check(Offset(["es"], "en"), t, "run_1", PB) == []


def test_confusions_follow_the_probed_rate() -> None:
    rates = [Fraction(25), Fraction(24), Fraction(24000, 1001)]
    at24 = {round(s, 5) for s, _ in confusions(N24, rates)}
    assert {0.04167, -0.04} <= at24  # 25/24 - 1 and 24/25 - 1
    assert 0.001 in {round(s, 3) for s, _ in confusions(NTSC, rates)}  # 24 vs 24000/1001
    assert all(
        s != 0.0 for s, _ in confusions(N24, rates)
    )  # the picture's own rate is no confusion


def test_recheck_and_inputs() -> None:
    check = Drift(["es"], "en")
    t = tl(N24, ratio=25 / 24)
    (flag,) = run_check(check, t, "run_1", PB)
    assert check.recheck(flag, t) is True
    assert check.recheck(flag, tl(N24)) is False  # the drift is gone
    assert Drift in CHECKS
    assert not Drift.active({Input.SOURCE_SUBS, Input.TARGET_SUBS})  # no picture: rate unknown
    assert Drift.active({Input.SOURCE_SUBS, Input.TARGET_SUBS, Input.PICTURE})


def test_one_unit_per_target_track() -> None:
    (u,) = Drift(["es"], "en").units(tl(N24))
    assert u.key == "E1/es/sync" and len(u.spans) == 150 and len(u.context) == 150
