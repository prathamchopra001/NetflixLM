"""`loc.shot_change`: a cue in or out point 1..11 frames from a shot change.

architecture.md > Rule pack defaults: cues starting within 1/2 s after a cut start on the cut, cues
ending within 1/2 s before one extend to it "keeping the 2-frame gap"; a point that is close to a
cut but not on it is flagged, on either side of the cut. An out point at the cut, or up to the
readability pack's `min_gap_frames` before it, is the prescribed position (the next cue starts on
the cut, so the gap rule asks for exactly that) and passes. The window is
`ceil(fps * timing.shot_change_window_s) - 1` frames of the probed rate (11 at 24 fps and at
24000/1001). A cue's out point is the exclusive end frame, a cut is the first frame of a shot.
Needs the picture: without it the check is not active (the pipeline reports it as skipped), it
never passes silently.
"""

import math
from collections.abc import Iterable
from fractions import Fraction
from pathlib import Path
from typing import Any

from nip.agents.base import Check, Finding, Input, WorkUnit, cue_windows
from nip.agents.localization.readability import rule_pack
from nip.contracts import refs
from nip.contracts.flag import CheckId, Evidence, EvidenceKind, EvidenceRole, Flag
from nip.contracts.timeline import Span, Timeline

SEVERITY = 3  # should fix
CONFIDENCE = 1.0  # pure rule


def window_frames(fps: Fraction, window_s: Fraction) -> int:
    """Largest distance (frames) that still counts as 'within the window' (strictly less than)."""
    return math.ceil(fps * window_s) - 1


def cuts_of(tl: Timeline) -> list[Span]:
    """The shots that start at a cut: every shot but the first (a cut is its first frame)."""
    return [s for s in tl.of(EvidenceKind.SHOT) if s.frames and int(refs.parse(s.ref).id) > 0]


class ShotChange(Check):
    check = CheckId.LOC_SHOT_CHANGE
    requires = frozenset({Input.PICTURE, Input.TARGET_SUBS})
    version = "1"

    def __init__(self, langs: Iterable[str], root: Path | None = None):
        packs = {lang: rule_pack(lang, root) for lang in langs}
        self.window_s = {lang: p.get("timing", {}) for lang, p in packs.items()}
        self.min_gap = {
            lang: int(p.get("readability", {}).get("min_gap_frames", 0))
            for lang, p in packs.items()
        }
        for lang, r in self.window_s.items():
            if "shot_change_window_s" not in r:
                raise ValueError(f"no timing rule pack for language {lang!r}")

    def units(self, tl: Timeline) -> list[WorkUnit]:
        """Cue windows; the context is the shots (cuts) near each window."""
        fps = Fraction(*tl.fps)
        cuts = cuts_of(tl)
        out = []
        for lang, r in self.window_s.items():
            w = window_frames(fps, Fraction(str(r["shot_change_window_s"])))
            for u in cue_windows(tl, lang):
                frames = [f for c in u.spans if c.frames for f in c.frames]
                near = tuple(
                    s
                    for s in cuts
                    if s.frames and min(frames) - w <= s.frames[0] <= max(frames) + w
                )
                out.append(WorkUnit(u.key, u.spans, near))
        return out

    def params(self) -> dict[str, Any]:
        return {"rules": self.window_s, "min_gap": self.min_gap}

    def run(self, unit: WorkUnit, tl: Timeline) -> list[Finding]:
        fps = Fraction(*tl.fps)
        return [
            f for c in unit.spans if (f := self.finding(c, list(unit.context), fps)) is not None
        ]

    def finding(self, cue: Span, cuts: list[Span], fps: Fraction) -> Finding | None:
        """The finding for `cue` against `cuts` (shots starting at a cut), or None."""
        assert cue.lang is not None and cue.frames is not None
        w = window_frames(fps, Fraction(str(self.window_s[cue.lang]["shot_change_window_s"])))
        found: list[tuple[str, int, Span]] = []
        for edge, frame in (("in", cue.frames[0]), ("out", cue.frames[1])):
            near = [(abs(frame - c.frames[0]), c) for c in cuts if c.frames]
            d, c = min(near, key=lambda t: t[0], default=(w + 1, None))
            if 1 <= d <= w and c is not None and c.frames is not None:
                before_gap = edge == "out" and 0 <= c.frames[0] - frame <= self.min_gap[cue.lang]
                if not before_gap:  # out point at the cut or the gap before it: as prescribed
                    found.append((edge, frame - c.frames[0], c))
        if not found:
            return None
        idx = refs.parse(cue.ref).id
        what = "; ".join(
            f"{edge}-point {abs(d)} frames {'after' if d > 0 else 'before'} the cut at "
            f"{c.tc_in or c.frames[0] if c.frames else ''}"
            for edge, d, c in found
        )
        evidence = [Evidence(kind=cue.kind, ref=cue.ref, role=EvidenceRole.CLAIM, quote=cue.text)]
        evidence += [
            Evidence(kind=c.kind, ref=c.ref, role=EvidenceRole.CONTEXT)
            for c in {c.ref: c for _, _, c in found}.values()
        ]
        return Finding(
            severity=SEVERITY,
            confidence=CONFIDENCE,
            title=f"Cue {idx}: {what}",
            explanation=(
                f"Cue {idx} ({cue.lang}) has a point that is close to a shot change but not on it: "
                f"{what}. Start on the cut, or end on it, keeping the 2-frame gap."
            ),
            evidence=evidence,
            lang=cue.lang,
        )

    def recheck(self, flag: Flag, tl: Timeline) -> bool:
        claim = next(e for e in flag.evidence if e.role is EvidenceRole.CLAIM)
        cue = tl.resolve(claim.ref)
        if (
            cue is None
            or cue.kind is not EvidenceKind.SUBTITLE_CUE
            or cue.lang not in self.window_s
        ):
            return False
        f = self.finding(cue, cuts_of(tl), Fraction(*tl.fps))
        return f is not None and f.title == flag.title
