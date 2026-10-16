"""Frame <-> SMPTE <-> ms math. Pure functions, stdlib only (data-model.md > Time, D-030).

Frame rates are exact `Fraction`s (24000/1001, never 23.976). Frames are ints, 0 = first frame.
SMPTE labels count at the nominal integer rate (round(fps)); drop-frame (`;`) only at 30000/1001
and 60000/1001 and skips 2 (resp. 4) labels per minute except every 10th minute.
"""

import re
from fractions import Fraction
from math import floor

_DROP = {Fraction(30000, 1001): 2, Fraction(60000, 1001): 4}
_TC = re.compile(r"(\d+):([0-5]\d):([0-5]\d)([:;])(\d+)")


def _round(x: Fraction) -> int:
    """Round half up (deterministic, monotone; Python's round() is half-even)."""
    return floor(x + Fraction(1, 2))


def _drop(fps: Fraction, drop: bool) -> int:
    if not drop:
        return 0
    if fps not in _DROP:
        raise ValueError(f"drop-frame needs 30000/1001 or 60000/1001, got {fps}")
    return _DROP[fps]


def ms_to_frame(ms: int | Fraction, fps: Fraction) -> int:
    """data-model.md: frame = round(ms * fps_num / (1000 * fps_den))."""
    return _round(Fraction(ms) * fps / 1000)


def frame_to_ms(frame: int, fps: Fraction) -> int:
    """Start of `frame` in whole ms (round half up)."""
    return _round(frame * 1000 / fps)


def frame_middle_seconds(frame: int, fps: Fraction) -> Fraction:
    """Seek target for the evidence player (D-029): (n + 0.5) / fps."""
    return (frame + Fraction(1, 2)) / fps


def frame_to_smpte(frame: int, fps: Fraction, drop: bool = False) -> str:
    if frame < 0:
        raise ValueError("negative frame")
    nominal, d = round(fps), _drop(fps, drop)
    if d:
        per_min, per_10 = nominal * 60 - d, nominal * 600 - 9 * d
        tens, rem = divmod(frame, per_10)
        frame += 9 * d * tens + (d * ((rem - d) // per_min) if rem > d else 0)
    ff = frame % nominal
    s = frame // nominal
    return f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}{';' if d else ':'}{ff:02d}"


def smpte_to_frame(tc: str, fps: Fraction) -> int:
    """Parse `HH:MM:SS:FF` (NDF) or `HH:MM:SS;FF` (DF; the `;` selects drop-frame)."""
    m = _TC.fullmatch(tc)
    if not m:
        raise ValueError(f"bad timecode {tc!r}")
    h, mi, s, sep, f = int(m[1]), int(m[2]), int(m[3]), m[4], int(m[5])
    nominal, d = round(fps), _drop(fps, sep == ";")
    if f >= nominal:
        raise ValueError(f"frame field {f} >= {nominal} in {tc!r}")
    if d and s == 0 and f < d and mi % 10:
        raise ValueError(f"{tc!r} is a dropped label")
    minutes = 60 * h + mi
    return (minutes * 60 + s) * nominal + f - d * (minutes - minutes // 10)
