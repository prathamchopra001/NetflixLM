"""Episode report — api-contracts.md › GET /shows/{show}/episodes/{ep}/report; ranking from
architecture.md › Report order (consequence, then severity, then confidence)."""

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Annotated, Literal

from pydantic import Field

from nip.contracts._base import Confidence, Contract
from nip.contracts.flag import Agent, Category, CheckId, EvidenceRole, Flag, FlagStatus, Tier
from nip.contracts.plan import Mode, Slot

RunStatus = Literal["queued", "running", "completed", "completed_with_gaps", "failed", "cancelled"]

# Consequence order of report sections.
SECTION_ORDER = [Category.CLEARANCE, Category.CONTINUITY, Category.LOCALIZATION, Category.PLOT_HOLE]


class FlagSummary(Contract):
    id: str | None  # None until the flag is persisted
    check: CheckId
    severity: Annotated[int, Field(ge=1, le=5)]
    confidence: Confidence
    tier: Tier
    title: str
    lang: str | None
    primary_tc: str | None  # first claim's tc_in, or its scene label in script-estimate mode
    status: FlagStatus


class ReportPlan(Contract):
    plan_id: str
    mode: Mode
    judge_independent: bool
    # Slots the planner could not place and its warnings (why: free vs needed VRAM), plus what
    # the run did without them; a skipped slot is never silent (architecture.md, W-serve).
    skipped_slots: list[Slot] = []
    warnings: list[str] = []


class ReportSection(Contract):
    category: Category
    flags: list[FlagSummary]


class Report(Contract):
    episode: str
    run_id: str
    status: RunStatus
    plan: ReportPlan
    coverage: dict[Agent, Confidence]  # fraction of work units done per agent
    counts: dict[Tier, int]
    sections: list[ReportSection]


def summarize(flag: Flag) -> FlagSummary:
    claim = next(e for e in flag.evidence if e.role is EvidenceRole.CLAIM)
    return FlagSummary(
        id=flag.id,
        check=flag.check,
        severity=flag.severity,
        confidence=flag.confidence,
        tier=flag.tier,
        title=flag.title,
        lang=flag.lang,
        primary_tc=claim.tc_in or claim.scene,
        status=flag.status,
    )


def build_report(
    *,
    episode: str,
    run_id: str,
    status: RunStatus,
    plan: ReportPlan,
    coverage: Mapping[Agent, float],
    flags: Iterable[Flag],
    include_suppressed: bool = False,
) -> Report:
    """Ranked report for one episode. Counts always include suppressed flags."""
    flags = list(flags)
    counts = Counter(f.tier for f in flags)
    shown = sorted(
        (f for f in flags if include_suppressed or f.tier is not Tier.SUPPRESSED),
        key=lambda f: (-f.severity, -f.confidence),
    )
    return Report(
        episode=episode,
        run_id=run_id,
        status=status,
        plan=plan,
        coverage=dict(coverage),
        counts={t: counts[t] for t in Tier},
        sections=[
            ReportSection(category=c, flags=[summarize(f) for f in shown if f.category is c])
            for c in SECTION_ORDER
        ],
    )
