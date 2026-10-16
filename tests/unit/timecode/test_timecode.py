from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nip.timecode import (
    frame_middle_seconds,
    frame_to_ms,
    frame_to_smpte,
    ms_to_frame,
    smpte_to_frame,
)

F2398, F25 = Fraction(24000, 1001), Fraction(25)
F2997, F5994 = Fraction(30000, 1001), Fraction(60000, 1001)
DF_RATES = st.sampled_from([F2997, F5994])
ANY_RATES = st.sampled_from(
    [F2398, Fraction(24), F25, F2997, Fraction(30), Fraction(50), F5994, Fraction(60)]
)
FRAMES = st.integers(0, 24 * 3600 * 60)


def test_known_values() -> None:
    assert smpte_to_frame("00:01:00;02", F2997) == 1800
    assert smpte_to_frame("00:00:59;29", F2997) == 1799
    assert smpte_to_frame("00:10:00;00", F2997) == 17982
    assert smpte_to_frame("01:00:00;00", F2997) == 107892
    assert smpte_to_frame("01:00:00:00", F2997) == 108000  # NDF label count at 29.97
    assert smpte_to_frame("01:00:00:00", F2398) == 86400
    assert smpte_to_frame("00:01:00;04", F5994) == 3600
    assert frame_to_smpte(1800, F2997, drop=True) == "00:01:00;02"
    assert frame_to_smpte(1799, F2997, drop=True) == "00:00:59;29"
    assert frame_to_smpte(17982, F2997, drop=True) == "00:10:00;00"
    assert frame_to_smpte(1800, F2997) == "00:01:00:00"
    assert frame_to_smpte(1440, F2398) == "00:01:00:00"


def test_ms_frame_known() -> None:
    assert ms_to_frame(1001, F2398) == 24  # one 23.976 second = 24 frames
    assert ms_to_frame(0, F2398) == 0
    assert ms_to_frame(3_603_600, F2398) == 86400  # 01:00:00:00 at 23.976 is 3603.6 s
    assert frame_to_ms(24, F2398) == 1001
    assert frame_middle_seconds(0, F2398) == Fraction(1001, 48000)
    assert frame_middle_seconds(10, F2398) == Fraction(21 * 1001, 48000)


def test_rejects() -> None:
    with pytest.raises(ValueError):
        frame_to_smpte(0, F2398, drop=True)
    with pytest.raises(ValueError):
        smpte_to_frame("00:01:00;01", F2997)  # dropped label
    with pytest.raises(ValueError):
        smpte_to_frame("00:00:00:30", F2997)
    with pytest.raises(ValueError):
        smpte_to_frame("1:2:3", F2997)
    with pytest.raises(ValueError):
        frame_to_smpte(-1, F25)


@given(FRAMES, ANY_RATES)
def test_ndf_roundtrip(frame: int, fps: Fraction) -> None:
    assert smpte_to_frame(frame_to_smpte(frame, fps), fps) == frame


@given(FRAMES, DF_RATES)
def test_df_roundtrip(frame: int, fps: Fraction) -> None:
    tc = frame_to_smpte(frame, fps, drop=True)
    assert ";" in tc
    assert smpte_to_frame(tc, fps) == frame


@given(FRAMES, DF_RATES)
def test_df_skip_rules(frame: int, fps: Fraction) -> None:
    """Never emit a dropped label: frames 0..d-1 at second 0 of any minute not divisible by 10."""
    d = 2 if fps == F2997 else 4
    tc = frame_to_smpte(frame, fps, drop=True)
    _, mm, ss, ff = (int(p) for p in tc.replace(";", ":").split(":"))
    assert not (ss == 0 and ff < d and mm % 10)


@given(st.integers(0, 24 * 3600 * 60 - 1), DF_RATES)
def test_df_monotone_step(frame: int, fps: Fraction) -> None:
    a = frame_to_smpte(frame, fps, drop=True)
    b = frame_to_smpte(frame + 1, fps, drop=True)
    assert a < b  # fixed-width strings, below 100 h


@given(st.integers(0, 10**8), ANY_RATES)
def test_ms_to_frame_monotone(ms: int, fps: Fraction) -> None:
    assert ms_to_frame(ms, fps) <= ms_to_frame(ms + 1, fps)
    assert frame_to_ms(ms, fps) < frame_to_ms(ms + 1, fps)


@given(FRAMES, ANY_RATES)
def test_frame_ms_roundtrip(frame: int, fps: Fraction) -> None:
    """Exact while ms are finer than frames (fps <= 60)."""
    assert ms_to_frame(frame_to_ms(frame, fps), fps) == frame


@given(FRAMES, ANY_RATES)
def test_frame_middle_inside_frame(frame: int, fps: Fraction) -> None:
    t = frame_middle_seconds(frame, fps)
    assert frame / fps < t < (frame + 1) / fps
    # ms_to_frame rounds to the nearest frame *start*; a frame middle is an exact tie -> n + 1
    assert ms_to_frame(t * 1000, fps) == frame + 1
