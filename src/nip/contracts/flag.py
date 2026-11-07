"""Flag and Evidence — docs/data-model.md › Flag and Evidence, Check IDs."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from nip.contracts._base import Confidence, Contract, FrameRange


class Agent(StrEnum):
    LOCALIZATION_AUDITOR = "localization_auditor"
    CLEARANCE_SCANNER = "clearance_scanner"
    SCRIPT_CRITIC = "script_critic"
    CONTINUITY_INSPECTOR = "continuity_inspector"


class Category(StrEnum):
    CLEARANCE = "clearance"
    CONTINUITY = "continuity"
    LOCALIZATION = "localization"
    PLOT_HOLE = "plot_hole"


class CheckId(StrEnum):
    LOC_TERM = "loc.term"
    LOC_GENDER = "loc.gender"
    LOC_FORMALITY = "loc.formality"
    LOC_SPOILER = "loc.spoiler"
    LOC_READABILITY = "loc.readability"
    LOC_SHOT_CHANGE = "loc.shot_change"
    LOC_DRIFT = "loc.drift"
    LOC_OFFSET = "loc.offset"
    CLR_PHONE = "clr.phone"
    CLR_URL = "clr.url"
    CLR_EMAIL = "clr.email"
    CLR_ADDRESS = "clr.address"
    CLR_PLATE = "clr.plate"
    CLR_BRAND_TEXT = "clr.brand_text"
    CLR_LOGO = "clr.logo"
    CLR_ARTWORK = "clr.artwork"
    CLR_DIALOGUE_REF = "clr.dialogue_ref"
    PLOT_KNOWLEDGE_ORDER = "plot.knowledge_order"
    PLOT_DEAD_ACTS = "plot.dead_acts"
    PLOT_TWO_PLACES = "plot.two_places"
    PLOT_PROP_PROVENANCE = "plot.prop_provenance"
    PLOT_MOTIVATION = "plot.motivation"
    PLOT_UNRESOLVED_SETUP = "plot.unresolved_setup"
    CONT_WARDROBE_TEXT = "cont.wardrobe_text"
    CONT_INJURY_TEXT = "cont.injury_text"
    CONT_PROP_TEXT = "cont.prop_text"
    CONT_VISUAL = "cont.visual"


# Check-ID prefix → the agent that owns it and the report category it lands in.
CHECK_OWNER: dict[str, tuple[Agent, Category]] = {
    "loc": (Agent.LOCALIZATION_AUDITOR, Category.LOCALIZATION),
    "clr": (Agent.CLEARANCE_SCANNER, Category.CLEARANCE),
    "plot": (Agent.SCRIPT_CRITIC, Category.PLOT_HOLE),
    "cont": (Agent.CONTINUITY_INSPECTOR, Category.CONTINUITY),
}

# Script Critic Layer 2 flags need at least two evidence items.
LAYER2_CHECKS = {CheckId.PLOT_MOTIVATION, CheckId.PLOT_UNRESOLVED_SETUP}


class Tier(StrEnum):
    MUST_REVIEW = "must_review"
    REVIEW_RECOMMENDED = "review_recommended"
    SUPPRESSED = "suppressed"


class FlagStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISPOSITIONED = "dispositioned"


class EvidenceKind(StrEnum):
    SCENE = "scene"
    SCRIPT_LINE = "script_line"
    SHOT = "shot"
    KEYFRAME = "keyframe"
    TRANSCRIPT_SEGMENT = "transcript_segment"
    SUBTITLE_CUE = "subtitle_cue"
    FACT = "fact"
    CLEARANCE_ITEM = "clearance_item"
    DETECTION = "detection"


class EvidenceRole(StrEnum):
    CLAIM = "claim"
    CONTEXT = "context"
    CONTRADICTION = "contradiction"
    SETUP = "setup"
    PAYOFF = "payoff"
    EXPECTED = "expected"


class Crop(Contract):
    keyframe: str
    box: Annotated[list[float], Field(min_length=4, max_length=4)]  # normalized [x, y, w, h]


class Evidence(Contract):
    kind: EvidenceKind
    ref: str  # docs/data-model.md › Evidence Refs, e.g. "S01E03/kf/118.0"
    role: EvidenceRole
    frames: FrameRange | None = None  # source of truth; tc_in/tc_out are display only
    lang: str | None = None
    tc_in: str | None = None
    tc_out: str | None = None
    scene: str | None = None  # script-estimate mode replaces tc_in/tc_out with this
    quote: str | None = None
    crop: Crop | None = None


class ProducedBy(Contract):
    model_variant: str | None
    prompt_version: str | None = None
    plan_id: str
    cache_key: str | None = None


VerificationResult = Literal["pass", "fail", "n/a"]


class Verification(Contract):
    evidence: VerificationResult = "n/a"
    rule_recheck: VerificationResult = "n/a"
    judge: VerificationResult = "n/a"
    judge_variant: str | None = None


class DispositionAction(StrEnum):
    ACCEPTED = "accepted"
    FIX_RERUN = "fix_rerun"
    OVERRIDDEN = "overridden"


class Disposition(Contract):
    action: DispositionAction
    note: str | None = None
    actor: str
    at: datetime

    @model_validator(mode="after")
    def _override_needs_note(self) -> Self:
        if self.action is DispositionAction.OVERRIDDEN and not self.note:
            raise ValueError("an overridden disposition requires a note")
        return self


class Flag(Contract):
    id: str | None = None  # "flg_48213"; assigned when persisted
    run_id: str
    episode: str
    agent: Agent
    check: CheckId
    category: Category
    lang: str | None = None
    severity: Annotated[int, Field(ge=1, le=5)]
    confidence: Confidence
    tier: Tier
    title: str
    explanation: str
    suggested_fix: str | None = None
    evidence: Annotated[list[Evidence], Field(min_length=1)]
    produced_by: ProducedBy
    verification: Verification = Field(default_factory=Verification)  # n/a until verification runs
    status: FlagStatus = FlagStatus.OPEN
    disposition: Disposition | None = None

    @model_validator(mode="after")
    def _rules(self) -> Self:
        agent, category = CHECK_OWNER[self.check.split(".")[0]]
        if (self.agent, self.category) != (agent, category):
            raise ValueError(f"{self.check} belongs to agent {agent} / category {category}")
        if not any(e.role is EvidenceRole.CLAIM for e in self.evidence):
            raise ValueError("evidence needs at least one item with role 'claim'")
        if self.check in LAYER2_CHECKS and len(self.evidence) < 2:
            raise ValueError(f"{self.check} needs at least two evidence items")
        return self
