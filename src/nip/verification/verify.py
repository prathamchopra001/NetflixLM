"""Verification, Phase 1 subset (architecture.md > Stage 5): evidence resolver + rule re-check.

Each step can only drop: a dropped flag is returned with its logged reason. The LLM judge and
routing/dedup steps come with the first LLM-originated check.
"""

import logging
from collections.abc import Callable, Iterable, Mapping

from nip.contracts.flag import CheckId, Flag
from nip.contracts.timeline import Timeline

log = logging.getLogger(__name__)

# A rule-originated check's re-check: True when the finding still reproduces on `tl`.
Recheck = Callable[[Flag, Timeline], bool]


def evidence_problem(flag: Flag, tl: Timeline) -> str | None:
    """Step 1: why the flag's evidence fails to resolve, or None when every item resolves."""
    for ev in flag.evidence:
        span = tl.resolve(ev.ref)
        if span is None or span.kind is not ev.kind:
            return f"evidence {ev.ref} does not resolve"
        if ev.frames != span.frames:
            return f"evidence {ev.ref} frames {ev.frames} differ from the timeline {span.frames}"
        if ev.quote is not None and ev.quote not in span.text:
            return f"evidence {ev.ref} quote does not match the stored text"
        if span.frames is not None and not (
            0 <= span.frames[0] < span.frames[1] <= tl.duration_frames
        ):
            return f"evidence {ev.ref} frames {span.frames} fall outside the episode"
    return None


def verify(
    flags: Iterable[Flag], tl: Timeline, rechecks: Mapping[CheckId, Recheck]
) -> tuple[list[Flag], list[tuple[Flag, str]]]:
    """(kept flags, [(dropped flag, reason)]); both carry their `verification` results."""
    kept: list[Flag] = []
    dropped: list[tuple[Flag, str]] = []
    for f in flags:
        reason = evidence_problem(f, tl)
        recheck = rechecks.get(f.check)
        v = {"evidence": "fail" if reason else "pass", "rule_recheck": "n/a"}
        if reason is None and recheck is not None:
            v["rule_recheck"] = "pass" if recheck(f, tl) else "fail"
            if v["rule_recheck"] == "fail":
                reason = "rule re-check no longer reproduces the finding"
        f = f.model_copy(update={"verification": f.verification.model_copy(update=v)})
        if reason is None:
            kept.append(f)
        else:
            log.warning("verification dropped %s flag %r: %s", f.check, f.title, reason)
            dropped.append((f, reason))
    return kept, dropped
