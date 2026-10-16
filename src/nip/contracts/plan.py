"""Plan — the planner's output (docs/hardware-adaptation.md › The Plan)."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from nip.contracts._base import Contract


class Slot(StrEnum):
    TEXT_LLM = "text_llm"
    VLM = "vlm"
    JUDGE_LLM = "judge_llm"
    ASR = "asr"
    OCR = "ocr"
    DETECTOR = "detector"
    IMAGE_EMBEDDER = "image_embedder"
    TEXT_EMBEDDER = "text_embedder"
    NER = "ner"
    SHOT_DETECTOR = "shot_detector"


class Objective(StrEnum):
    QUALITY = "quality"
    THROUGHPUT = "throughput"


class Mode(StrEnum):
    STAGED = "staged"
    RESIDENT = "resident"


class StageGroup(Contract):
    name: str
    slots: list[Slot]


class SlotDecision(Contract):
    variant: str
    shared_with: list[Slot] | None = None
    replicas: int | None = None
    gpus_per_replica: int | None = None
    gpu_fraction: float | None = None
    context: int | None = None
    gpu_memory_utilization: float | None = None
    kv_cache_bytes: int | None = None  # exact vLLM KV budget (--kv-cache-memory-bytes)
    max_pixels: int | None = None
    images_per_prompt: int | None = None
    independent_family: bool | None = None  # judge_llm only


class Amendment(Contract):
    at: datetime
    slot: Slot
    from_: str = Field(alias="from")
    to: str
    reason: str


class Plan(Contract):
    plan_id: str | None = None  # "plan_42"; assigned when persisted
    inventory_fingerprint: str
    catalog_sha256: str
    objective: Objective
    mode: Mode
    groups: list[StageGroup]
    decisions: dict[Slot, SlotDecision]
    pins: dict[Slot, str] = {}
    skipped_slots: list[Slot] = []
    warnings: list[str] = []
    amendments: list[Amendment] = []
