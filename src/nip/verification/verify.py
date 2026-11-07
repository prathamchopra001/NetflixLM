"""Verification, Phase 1 subset (architecture.md > Stage 5): evidence resolver + rule re-check.

Each step can only drop: a dropped flag is returned with its logged reason. The LLM judge and
routing/dedup steps come with the first LLM-originated check.
"""

import logging
from collections.abc import Iterable
from typing import Protocol

from nip.contracts.flag import CheckId, Flag
from nip.contracts.timeline import Timeline

log = logging.getLogger(__name__)


class Verifiable(Protocol):
    """What verification needs from a check (`nip.agents.base.Check` has it; no agents import)."""

    @property
    def check(self) -> CheckId: ...

    @property
    def rule_originated(self) -> bool: ...

    def recheck(self, flag: Flag, tl: Timeline) -> bool | None: ...


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


def recheck_problem(flag: Flag, tl: Timeline, check: Verifiable | None) -> str | None:
    """Step 2, failing closed: why a rule-originated flag does not reproduce on `tl`, or None."""
    if check is None:
        return f"no {flag.check} check was given to verification"
    ok = check.recheck(flag, tl)
    if ok is None:
        return f"rule-originated check {flag.check} has no rule re-check"
    return None if ok else "rule re-check no longer reproduces the finding"


def verify(
    flags: Iterable[Flag], tl: Timeline, checks: Iterable[Verifiable]
) -> tuple[list[Flag], list[tuple[Flag, str]]]:
    """(kept flags, [(dropped flag, reason)]); both carry their `verification` results.

    `checks` are the checks that produced `flags`: a flag whose check is missing, or whose
    rule-originated check has no `recheck`, is dropped.
    """
    by_id = {c.check: c for c in checks}
    kept: list[Flag] = []
    dropped: list[tuple[Flag, str]] = []
    for f in flags:
        reason = evidence_problem(f, tl)
        v = {"evidence": "fail" if reason else "pass", "rule_recheck": "n/a"}
        check = by_id.get(f.check)
        if reason is None and (check is None or check.rule_originated):
            reason = recheck_problem(f, tl, check)
            v["rule_recheck"] = "fail" if reason else "pass"
        f = f.model_copy(update={"verification": f.verification.model_copy(update=v)})
        if reason is None:
            kept.append(f)
        else:
            log.warning("verification dropped %s flag %r: %s", f.check, f.title, reason)
            dropped.append((f, reason))
    return kept, dropped
