"""`loc.drift` and `loc.offset`: a target track that is out of sync with the source track.

architecture.md > Agent 1 > Sync drift: regress (target start - source start) on episode time
(`nip.timeline.cue_align.Fit`). A slope near 4.2% means 25 fps timing on a 24 fps picture, near 0.1%
SMPTE-24 timecode confused with 23.976 media time; a constant offset is a sync offset. Slopes are
compared with `rate / picture fps - 1` for every rate in the rule pack's `timing.sync_rates`, never
with a constant. Both flags are track-level (R12): they claim the first and the last cue of the
track, so a label that lists every cue of the track matches either.
"""

from collections.abc import Iterable
from fractions import Fraction
from pathlib import Path
from typing import Any, ClassVar

from nip.agents.base import Check, Finding, Input, WorkUnit
from nip.agents.localization.readability import rule_pack
from nip.contracts.flag import CheckId, Evidence, EvidenceKind, EvidenceRole, Flag
from nip.contracts.timeline import Span, Timeline
from nip.timeline.cue_align import Fit, aligned, track

SEVERITY = 4  # must fix before release
CONFIDENCE = 0.99  # a fitted line, not an inference about meaning
UNCLASSIFIED = 0.9  # drift that matches no known confusion


def rate(r: Fraction) -> str:
    return f"{float(r):.3f}".rstrip("0").rstrip(".")


def confusions(fps: Fraction, rates: Iterable[Fraction]) -> list[tuple[float, str]]:
    """(slope, cause) of every known frame-rate confusion for a picture of rate `fps`: a track
    timed for `r` fps has slope r/fps - 1, one timed the other way round fps/r - 1."""
    out = []
    for r in rates:
        if r != fps:
            out.append((float(r / fps - 1), f"timing for a {rate(r)} fps picture"))
            out.append(
                (float(fps / r - 1), f"timing of a {rate(r)} fps picture read as {rate(fps)}")
            )
    return out


class _Sync(Check):
    # Both need the picture: the drift is classified against its probed rate, and an offset is
    # reported in frames of it (without a picture the timeline's rate is only an assumed 24).
    requires: ClassVar[frozenset[Input]] = frozenset(
        {Input.SOURCE_SUBS, Input.TARGET_SUBS, Input.PICTURE}
    )
    version = "1"

    def __init__(self, langs: Iterable[str], source_lang: str, root: Path | None = None):
        self.source_lang = source_lang
        self.rules = {lang: rule_pack(lang, root).get("timing", {}) for lang in langs}
        for lang, r in self.rules.items():
            if "drift_min_slope" not in r:
                raise ValueError(f"no timing rule pack for language {lang!r}")

    def units(self, tl: Timeline) -> list[WorkUnit]:
        """One unit per target track: the whole track (and the whole source track as context)."""
        return [
            WorkUnit(f"{tl.episode}/{lang}/sync", tuple(cues), tuple(track(tl, self.source_lang)))
            for lang in self.rules
            if (cues := track(tl, lang))
        ]

    def params(self) -> dict[str, Any]:
        return {"source_lang": self.source_lang, "rules": self.rules}

    def run(self, unit: WorkUnit, tl: Timeline) -> list[Finding]:
        lang = unit.spans[0].lang
        assert lang is not None
        f = self.finding(lang, tl)
        return [f] if f else []

    def finding(self, lang: str, tl: Timeline) -> Finding | None:
        al = aligned(tl, self.source_lang, lang)
        cues = track(tl, lang)
        if al.fit is None or not cues:
            return None
        return self.judge(lang, al.fit, Fraction(*tl.fps), cues, self.rules[lang])

    def judge(
        self, lang: str, fit: Fit, fps: Fraction, cues: list[Span], rules: dict[str, Any]
    ) -> Finding | None:
        raise NotImplementedError

    def recheck(self, flag: Flag, tl: Timeline) -> bool:
        """Re-fit the track: the same finding still comes out."""
        f = self.finding(flag.lang, tl) if flag.lang in self.rules else None
        return f is not None and f.title == flag.title

    def finding_for(self, lang: str, cues: list[Span], title: str, why: str, fix: str,
                    confidence: float) -> Finding:  # fmt: skip
        ends = [cues[0], cues[-1]] if len(cues) > 1 else cues[:1]
        return Finding(
            severity=SEVERITY,
            confidence=confidence,
            title=title,
            explanation=f"Track {lang}: {why}",
            evidence=[
                Evidence(kind=EvidenceKind.SUBTITLE_CUE, ref=c.ref, role=EvidenceRole.CLAIM,
                         quote=c.text) for c in ends
            ],
            suggested_fix=fix,
            lang=lang,
        )  # fmt: skip


def significant_slope(fit: Fit, rules: dict[str, Any]) -> bool:
    return abs(fit.slope) >= float(rules["drift_min_slope"]) and abs(
        fit.slope
    ) * fit.span_s >= float(Fraction(str(rules["drift_min_total_s"])))


class Drift(_Sync):
    check = CheckId.LOC_DRIFT

    def judge(
        self, lang: str, fit: Fit, fps: Fraction, cues: list[Span], rules: dict[str, Any]
    ) -> Finding | None:
        if not significant_slope(fit, rules):
            return None
        known = confusions(fps, (Fraction(str(r)) for r in rules["sync_rates"]))
        tol = float(rules["drift_match_tolerance"])
        slope, cause = min(known, key=lambda c: abs(fit.slope - c[0]))
        hit = abs(fit.slope - slope) <= tol * abs(slope)
        total = fit.slope * fit.span_s
        what = f"matches {cause}" if hit else "matches no known frame-rate confusion"
        return self.finding_for(
            lang,
            cues,
            f"Track drifts {fit.slope * 100:+.3f}% ({total:+.1f} s over {fit.span_s / 60:.0f} min)",
            f"target start - source start grows {fit.slope * 100:+.3f}% per second of episode "
            f"time ({fit.n} matched cues); the slope {what}.",
            f"Retime the track by x{1 / (1 + fit.slope):.5f}.",
            CONFIDENCE if hit else UNCLASSIFIED,
        )


class Offset(_Sync):
    check = CheckId.LOC_OFFSET

    def judge(
        self, lang: str, fit: Fit, fps: Fraction, cues: list[Span], rules: dict[str, Any]
    ) -> Finding | None:
        # With drift the constant term is the intercept; without it the median difference is the
        # steadier estimate.
        off = fit.intercept_s if significant_slope(fit, rules) else fit.median_s
        if abs(off) < float(Fraction(str(rules["offset_min_s"]))):
            return None
        frames = round(off * float(fps))
        return self.finding_for(
            lang,
            cues,
            f"Track is {frames:+d} frames ({off:+.3f} s) off the source",
            f"target cues start {off:+.3f} s ({frames:+d} frames at {rate(fps)} fps) after "
            f"their source cues ({fit.n} matched cues).",
            f"Shift every cue by {-frames:+d} frames.",
            CONFIDENCE,
        )
