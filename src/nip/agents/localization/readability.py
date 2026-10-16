"""`loc.readability`: deterministic timing & readability rules per language rule pack.

architecture.md > Agent 1 > Timing & readability: reading speed (CPS), characters per line, lines
per cue, min/max duration, min gap, overlaps. Shot-change rules are `loc.shot_change`. Durations
and gaps are measured in frames of the timeline (the picture's rate). One flag per cue lists every
rule it breaks; gap/overlap rules belong to the later cue and cite the earlier one as context.
"""

from collections.abc import Iterable
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml

from nip.agents.base import Check, Finding, Input, WorkUnit, cue_windows
from nip.contracts.flag import CheckId, Evidence, EvidenceKind, EvidenceRole, Flag
from nip.contracts.timeline import Span, Timeline

LANGUAGES = Path(__file__).resolve().parents[4] / "config" / "languages"
CONFIDENCE = 1.0  # pure rules: a violation is certain
SHOULD_FIX = 3  # breaks the style guide (data-model.md: 3 = should fix)
MINOR = 2  # a gap that should be closed


def rule_pack(lang: str, root: Path = LANGUAGES) -> dict[str, Any]:
    """Merged rule pack for `lang`: _base, then each tag prefix (es-ES -> _base, es, es-ES)."""
    parts = lang.split("-")
    pack: dict[str, Any] = {}
    for tag in ["_base", *("-".join(parts[: i + 1]) for i in range(len(parts)))]:
        f = root / f"{tag}.yaml"
        if f.exists():
            for section, values in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).items():
                pack[section] = {**pack.get(section, {}), **values}
    return pack


def violations(
    cue: Span, prev: Span | None, rules: dict[str, Any], fps: Fraction, audience: str = "adult"
) -> list[tuple[int, str, bool]]:
    """(severity, description, cites_prev) for every rule `cue` breaks; `prev` is the cue before."""
    assert cue.frames is not None
    a, b = cue.frames
    secs = Fraction(b - a) / fps
    lines = cue.text.split("\n")
    longest = max(len(ln) for ln in lines)
    cps = Fraction(len(cue.text.replace("\n", ""))) / secs
    max_cps, max_lines, max_chars = (
        rules["reading_speed_cps"][audience],
        rules["max_lines"],
        rules["max_chars_per_line"],
    )
    min_s, max_s = rules["min_duration_s"], rules["max_duration_s"]
    out = []
    if len(lines) > max_lines:
        out.append((SHOULD_FIX, f"{len(lines)} lines (max {max_lines})", False))
    if longest > max_chars:
        out.append((SHOULD_FIX, f"{longest} characters/line (max {max_chars})", False))
    if cps > max_cps:
        out.append((SHOULD_FIX, f"reading speed {float(cps):.1f} CPS (max {max_cps})", False))
    if secs < Fraction(str(min_s)):
        out.append((SHOULD_FIX, f"duration {float(secs):.2f} s (min {min_s} s)", False))
    if secs > Fraction(str(max_s)):
        out.append((SHOULD_FIX, f"duration {float(secs):.2f} s (max {max_s} s)", False))
    if prev is not None and prev.frames is not None:
        gap, min_gap = a - prev.frames[1], rules["min_gap_frames"]
        if gap < 0:
            out.append((SHOULD_FIX, f"overlaps the previous cue by {-gap} frames", True))
        elif gap < min_gap:
            out.append((SHOULD_FIX, f"gap of {gap} frames (min {min_gap})", True))
        elif min_gap < gap < Fraction(str(rules["close_gap_below_s"])) * fps:
            out.append((MINOR, f"gap of {gap} frames should be closed to {min_gap}", True))
    return out


class Readability(Check):
    check = CheckId.LOC_READABILITY
    requires = frozenset({Input.SOURCE_SUBS, Input.TARGET_SUBS})

    def __init__(self, langs: Iterable[str], audience: str = "adult", root: Path = LANGUAGES):
        self.audience = audience
        self.rules = {lang: rule_pack(lang, root).get("readability", {}) for lang in langs}
        for lang, r in self.rules.items():
            if "reading_speed_cps" not in r:
                raise ValueError(f"no readability rule pack for language {lang!r}")

    def units(self, tl: Timeline) -> list[WorkUnit]:
        return [u for lang in self.rules for u in cue_windows(tl, lang)]

    def run(self, unit: WorkUnit, tl: Timeline) -> list[Finding]:
        return [f for cue in unit.spans if (f := self.finding(cue, tl)) is not None]

    def finding(self, cue: Span, tl: Timeline) -> Finding | None:
        assert cue.lang is not None
        ep_lang, idx = cue.ref.rsplit("/", 1)
        prev = tl.resolve(f"{ep_lang}/{int(idx) - 1}")  # the cue before it in the file
        fps = Fraction(*tl.fps)
        found = violations(cue, prev, self.rules[cue.lang], fps, self.audience)
        if not found:
            return None
        evidence = [Evidence(kind=cue.kind, ref=cue.ref, role=EvidenceRole.CLAIM, quote=cue.text)]
        if prev is not None and any(p for _, _, p in found):
            evidence.append(
                Evidence(kind=prev.kind, ref=prev.ref, role=EvidenceRole.CONTEXT, quote=prev.text)
            )
        what = "; ".join(d for _, d, _ in found)
        return Finding(
            severity=max(s for s, _, _ in found),
            confidence=CONFIDENCE,
            title=f"Cue {idx}: {what}",
            explanation=(
                f"Cue {idx} ({cue.lang}) breaks the {cue.lang} rule pack ({self.audience}): {what}."
            ),
            evidence=evidence,
            lang=cue.lang,
        )

    def recheck(self, flag: Flag, tl: Timeline) -> bool:
        """Rule re-check (verification step 2): the claimed cue still breaks the same rules."""
        claim = next(e for e in flag.evidence if e.role is EvidenceRole.CLAIM)
        cue = tl.resolve(claim.ref)
        if cue is None or cue.kind is not EvidenceKind.SUBTITLE_CUE or cue.lang not in self.rules:
            return False
        f = self.finding(cue, tl)
        return f is not None and f.title == flag.title
