"""Structured metadata output schemas for recaps. Matches personalization interface contract."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ToneVariant(str, Enum):
    ACTION = "action"
    ROMANCE = "romance"
    SUSPENSE = "suspense"
    COMEDY = "comedy"
    CHARACTER_STUDY = "character_study"


class RecapVariantOutput(BaseModel):
    """A single tonal variant of a recap."""

    text: str
    tone: ToneVariant
    thread_focus: str
    emotional_valence: dict[str, float]


class NarrativeThread(BaseModel):
    """A primary narrative thread identified in an episode."""

    id: str
    label: str
    weight: float = Field(ge=0.0, le=1.0)
    genre_tags: list[str] = []


class EmotionalProfile(BaseModel):
    """Emotional characterization of an episode's recap output."""

    dominant_emotion: str
    emotion_vector: dict[str, float] = {}
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    trajectory: str = "neutral"


class CharacterFocus(BaseModel):
    """Character weighting for recap personalization."""

    primary: str
    secondary: list[str] = []
    weights: dict[str, float] = {}


class RecapMetadataOutput(BaseModel):
    """Full metadata payload for the personalization interface."""

    episode_ref: str
    show_id: str
    locale: str = "en-US"
    available_variants: list[str] = [t.value for t in ToneVariant]
    narrative_threads: list[NarrativeThread] = []
    emotional_profile: Optional[EmotionalProfile] = None
    character_focus: Optional[CharacterFocus] = None
    spoiler_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
