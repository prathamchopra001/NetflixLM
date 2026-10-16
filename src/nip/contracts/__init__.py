"""Shared Pydantic contracts (docs/data-model.md, docs/hardware-adaptation.md); pydantic only."""

from nip.contracts.fact import Fact, FactStatus, Predicate
from nip.contracts.flag import (
    Agent,
    Category,
    CheckId,
    Crop,
    Disposition,
    DispositionAction,
    Evidence,
    EvidenceKind,
    EvidenceRole,
    Flag,
    FlagStatus,
    ProducedBy,
    Tier,
    Verification,
)
from nip.contracts.inventory import Autoscaling, Gpu, HardwareInventory, Node
from nip.contracts.plan import Amendment, Mode, Objective, Plan, Slot, SlotDecision, StageGroup

__all__ = [
    "Agent",
    "Amendment",
    "Autoscaling",
    "Category",
    "CheckId",
    "Crop",
    "Disposition",
    "DispositionAction",
    "Evidence",
    "EvidenceKind",
    "EvidenceRole",
    "Fact",
    "FactStatus",
    "Flag",
    "FlagStatus",
    "Gpu",
    "HardwareInventory",
    "Mode",
    "Node",
    "Objective",
    "Plan",
    "Predicate",
    "ProducedBy",
    "Slot",
    "SlotDecision",
    "StageGroup",
    "Tier",
    "Verification",
]
