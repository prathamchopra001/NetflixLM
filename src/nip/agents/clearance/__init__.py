"""Clearance Scanner (architecture.md > Agent 2). On-screen text: `ocr_text` reads keyframes and
finds candidates (2.6); `stage` runs it as pipeline stage `clearance.ocr` and stores the result;
`matching` / `occurrences` / `checks` turn the stored candidates into occurrences and the six
clr.* flags; `report` writes the clearance report CSV. `CHECKS` lists the check classes."""

from nip.agents.base import Check
from nip.agents.clearance.checks import (
    ClearanceText,
    ClrAddress,
    ClrBrandText,
    ClrEmail,
    ClrPhone,
    ClrPlate,
    ClrUrl,
)

TEXT_CHECKS: list[type[ClearanceText]] = [
    ClrPhone, ClrUrl, ClrEmail, ClrAddress, ClrPlate, ClrBrandText
]  # fmt: skip
CHECKS: list[type[Check]] = list(TEXT_CHECKS)
