from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RelationType(str, Enum):
    AT_LOCATION = "AT_LOCATION"
    HOLDS_PROP = "HOLDS_PROP"
    KNOWS_SECRET = "KNOWS_SECRET"
    ALIVE_AT = "ALIVE_AT"
    RELATES_TO = "RELATES_TO"
    CONTAINS = "CONTAINS"
    STATE_OF = "STATE_OF"
    CAUSES = "CAUSES"
    PRECEDES = "PRECEDES"
    CONCEALED_FROM = "CONCEALED_FROM"


class Hand(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    UNSPECIFIED = "unspecified"


class SecretSource(str, Enum):
    WITNESS = "witness"
    TOLD = "told"
    INFERRED = "inferred"


class RelationCategory(str, Enum):
    PARENT = "parent"
    CHILD = "child"
    SPOUSE = "spouse"
    SIBLING = "sibling"
    FRIEND = "friend"
    ENEMY = "enemy"
    OTHER = "other"


class RelationBase(BaseModel):
    relation_type: RelationType
    source_id: str
    target_id: str
    timecode: Optional[str] = None
    episode_ref: Optional[str] = None
    confidence: float = 1.0

    def relation_id(self) -> str:
        return f"{self.relation_type.value}:{self.source_id}->{self.target_id}"


class AtLocationRelation(RelationBase):
    relation_type: RelationType = Field(default=RelationType.AT_LOCATION, init=False)
    timecode: str
    episode_ref: str


class HoldsPropRelation(RelationBase):
    relation_type: RelationType = Field(default=RelationType.HOLDS_PROP, init=False)
    timecode: str
    episode_ref: str
    hand: Hand = Hand.UNSPECIFIED


class KnowsSecretRelation(RelationBase):
    relation_type: RelationType = Field(default=RelationType.KNOWS_SECRET, init=False)
    since_tc: str
    source: SecretSource


class RelatesToRelation(RelationBase):
    relation_type: RelationType = Field(default=RelationType.RELATES_TO, init=False)
    relation: RelationCategory
    since_tc: Optional[str] = None


class ConcealedFromRelation(RelationBase):
    relation_type: RelationType = Field(default=RelationType.CONCEALED_FROM, init=False)
    until_tc: str
