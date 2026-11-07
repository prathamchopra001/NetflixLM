"""Check interface: required inputs, work units, flag emission (architecture.md › Stage 4).

A check declares the inputs it needs, splits the timeline into work units, and returns `Finding`s.
`run_check` turns findings into `Flag`s through `emit`, the one emission path every check shares:
it fills agent / category / tier, and resolves every evidence ref against the timeline, copying the
object's frames and display fields onto the evidence. A finding citing an object the timeline does
not have is dropped (D-005: no output without evidence).
"""

import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Collection
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar

from nip.contracts import refs
from nip.contracts.flag import (
    CHECK_OWNER,
    CheckId,
    Evidence,
    EvidenceKind,
    Flag,
    ProducedBy,
    Tier,
)
from nip.contracts.timeline import Span, Timeline

log = logging.getLogger(__name__)


class Input(StrEnum):
    """Columns of the activation matrix (architecture.md › Activation matrix)."""

    SCRIPT = "script"
    PICTURE = "picture"
    SOURCE_SUBS = "source_subs"
    TARGET_SUBS = "target_subs"
    BIBLE = "bible"
    GLOSSARY = "glossary"
    CLEARANCE_LOG = "clearance_log"


@dataclass(frozen=True)
class WorkUnit:
    """`spans` (checked) + `context` (read only) are everything `run` may read from the timeline,
    so together with the check's `version` and `params()` they are the unit's cache-key inputs."""

    key: str  # work_unit.unit_key, e.g. "S01E03/es-419/200-219"
    spans: tuple[Span, ...]  # the timeline objects this unit checks
    context: tuple[Span, ...] = ()  # objects it also reads but does not check (the cue before)


@dataclass
class Finding:
    """What a check reports; `emit` adds the fields every flag shares."""

    severity: int
    confidence: float
    title: str
    explanation: str
    evidence: list[Evidence]
    suggested_fix: str | None = None
    lang: str | None = None
    # Routing that confidence must not decide (B-064): a clearance item that is pending / denied is
    # `must_review` however low the confidence; a cleared one is `suppressed` (kept for the audit).
    tier: Tier | None = None


class Check(ABC):
    check: ClassVar[CheckId]
    requires: ClassVar[frozenset[Input]]  # ● inputs; the check runs only when all exist
    version: ClassVar[str]  # bump when the check's logic changes (stage-cache key)
    # Verification step 2 re-checks rule-originated flags; a rule check without `recheck` has
    # every flag dropped there (fail closed). LLM / vision checks set this False.
    rule_originated: ClassVar[bool] = True

    @classmethod
    def active(cls, available: Collection[Input]) -> bool:
        return cls.requires <= set(available)

    @abstractmethod
    def units(self, tl: Timeline) -> list[WorkUnit]: ...

    @abstractmethod
    def run(self, unit: WorkUnit, tl: Timeline) -> list[Finding]: ...

    def params(self) -> dict[str, Any]:
        """Configuration the findings depend on (rule packs, thresholds): stage-cache key input."""
        return {}

    def inputs(self, unit: WorkUnit, tl: Timeline) -> list[str]:
        """Hashes of what `run(unit)` reads besides the unit's spans, context and `params()` (the
        store, other episodes): stage-cache key inputs (2.9B). A check that reads anything else
        must say so here, or a cached unit replays findings computed from stale data."""
        return []

    def recheck(self, flag: Flag, tl: Timeline) -> bool | None:
        """Rule re-check: does `flag` still reproduce on `tl`? None: this check has none."""
        return None


def cue_windows(tl: Timeline, lang: str, size: int = 20) -> list[WorkUnit]:
    """Windows of `size` consecutive cues of one track, keyed `{ep}/{lang}/{first}-{last}`.

    The cue before each window is its read-only context (gap and overlap rules compare with it).
    """
    cues = tl.of(EvidenceKind.SUBTITLE_CUE, lang)
    out = []
    for i in range(0, len(cues), size):
        w = tuple(cues[i : i + size])
        first, last = (refs.parse(c.ref).id for c in (w[0], w[-1]))
        out.append(WorkUnit(f"{tl.episode}/{lang}/{first}-{last}", w, tuple(cues[i - 1 : i])))
    return out


def tier_for(confidence: float) -> Tier:
    """Review tier from confidence (architecture.md › Review tiers; NIP_TIER_* thresholds)."""
    if confidence >= float(os.environ.get("NIP_TIER_MUST_REVIEW", "0.90")):
        return Tier.MUST_REVIEW
    if confidence >= float(os.environ.get("NIP_TIER_REVIEW_RECOMMENDED", "0.70")):
        return Tier.REVIEW_RECOMMENDED
    return Tier.SUPPRESSED


def emit(
    finding: Finding, check: CheckId, tl: Timeline, run_id: str, produced_by: ProducedBy
) -> Flag | None:
    """The Flag for `finding`, or None (logged) when any evidence ref does not resolve."""
    evidence = []
    for ev in finding.evidence:
        span = tl.resolve(ev.ref)
        if span is None or span.kind is not ev.kind:
            log.warning("dropped %s finding: evidence %s does not resolve", check, ev.ref)
            return None
        evidence.append(
            ev.model_copy(
                update={
                    "frames": span.frames,
                    "tc_in": span.tc_in,
                    "tc_out": span.tc_out,
                    "scene": span.scene,
                    "lang": ev.lang or span.lang,
                }
            )
        )
    agent, category = CHECK_OWNER[check.split(".")[0]]
    return Flag(
        run_id=run_id,
        episode=tl.episode,
        agent=agent,
        check=check,
        category=category,
        lang=finding.lang,
        severity=finding.severity,
        confidence=finding.confidence,
        tier=finding.tier or tier_for(finding.confidence),
        title=finding.title,
        explanation=finding.explanation,
        suggested_fix=finding.suggested_fix,
        evidence=evidence,
        produced_by=produced_by,
    )


def run_check(check: Check, tl: Timeline, run_id: str, produced_by: ProducedBy) -> list[Flag]:
    """Run every work unit of `check` and emit its findings as flags."""
    flags = []
    for unit in check.units(tl):
        for finding in check.run(unit, tl):
            if (flag := emit(finding, check.check, tl, run_id, produced_by)) is not None:
                flags.append(flag)
    return flags
