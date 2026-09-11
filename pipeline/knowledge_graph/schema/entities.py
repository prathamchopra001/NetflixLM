from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    CHARACTER = "character"
    LOCATION = "location"
    PROP = "prop"
    EVENT = "event"
    SECRET = "secret"


class CharacterStatus(str, Enum):
    ALIVE = "alive"
    DEAD = "dead"
    UNKNOWN = "unknown"


class LocationType(str, Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    VEHICLE = "vehicle"


class PropCategory(str, Enum):
    WEAPON = "weapon"
    CLOTHING = "clothing"
    DEVICE = "device"
    VEHICLE = "vehicle"
    OTHER = "other"


class EventSignificance(str, Enum):
    MINOR = "minor"
    MAJOR = "major"
    CLIMACTIC = "climactic"


class SecretScope(str, Enum):
    PERSONAL = "personal"
    RELATIONAL = "relational"
    PLOT_CRITICAL = "plot-critical"


class EntityBase(BaseModel):
    entity_type: EntityType
    name: str
    first_appearance_tc: str
    description: Optional[str] = None

    def entity_id(self) -> str:
        return f"{self.entity_type.value}:{self.name}"


class CharacterEntity(EntityBase):
    entity_type: EntityType = Field(default=EntityType.CHARACTER, init=False)
    actor_name: Optional[str] = None
    status: CharacterStatus = CharacterStatus.ALIVE
    death_tc: Optional[str] = None


class LocationEntity(EntityBase):
    entity_type: EntityType = Field(default=EntityType.LOCATION, init=False)
    location_type: Optional[LocationType] = None


class PropEntity(EntityBase):
    entity_type: EntityType = Field(default=EntityType.PROP, init=False)
    category: Optional[PropCategory] = None
    current_state: Optional[str] = None


class EventEntity(EntityBase):
    entity_type: EntityType = Field(default=EntityType.EVENT, init=False)
    timecode: str
    episode_ref: str
    significance: EventSignificance = EventSignificance.MINOR


class SecretEntity(EntityBase):
    entity_type: EntityType = Field(default=EntityType.SECRET, init=False)
    revealed_tc: str
    revealed_in_episode: str
    scope: SecretScope = SecretScope.PERSONAL


_ENTITY_MAP: dict[EntityType, type[EntityBase]] = {
    EntityType.CHARACTER: CharacterEntity,
    EntityType.LOCATION: LocationEntity,
    EntityType.PROP: PropEntity,
    EntityType.EVENT: EventEntity,
    EntityType.SECRET: SecretEntity,
}


def create_entity(data: dict) -> EntityBase:
    entity_type = EntityType(data["entity_type"])
    cls = _ENTITY_MAP[entity_type]
    return cls(**data)
