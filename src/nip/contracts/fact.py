"""Fact — a consolidated, timed fact (docs/data-model.md › Knowledge layer, table `fact`)."""

from enum import StrEnum
from typing import Annotated, Any

from pydantic import Field

from nip.contracts._base import Confidence, Contract, OpenRange


class Predicate(StrEnum):
    PRESENT_AT = "present_at"
    HOLDS = "holds"
    OWNS = "owns"
    STATE = "state"
    WEARING = "wearing"
    LEARNS = "learns"
    REFERENCES = "references"
    RELATIONSHIP = "relationship"
    SETUP = "setup"
    PAYOFF = "payoff"
    DECISION = "decision"
    MENTIONS = "mentions"


class FactStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"


class Fact(Contract):
    id: int | None = None  # assigned when persisted; API ref is "fact/{id}"
    show_id: int
    predicate: Predicate
    subject_id: int
    object_id: int | None = None
    value: dict[str, Any] | None = None  # {"state": "injured", "detail": "left hand cut"}
    screen: OpenRange  # validity in viewer order (screen_key units)
    story: OpenRange  # validity in story order (story_seq units)
    source_event_ids: Annotated[list[int], Field(min_length=1)]
    confidence: Confidence
    version: Annotated[int, Field(ge=1)] = 1
    status: FactStatus = FactStatus.ACTIVE
    supersedes: int | None = None
