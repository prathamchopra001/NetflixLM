"""Shared parse result and decoding helpers for the ingest parsers."""

from dataclasses import dataclass, field
from typing import Any

from charset_normalizer import from_bytes


@dataclass(frozen=True)
class Issue:
    """One validation error: `reason` and (when known) the 1-based source `line`."""

    reason: str
    line: int | None = None


@dataclass
class Parsed[T]:
    """Parser output. `errors` reject the file (INPUT_REJECTED); `warnings` do not."""

    data: T | None = None
    errors: list[Issue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def rejection(self, message: str) -> dict[str, Any] | None:
        """INPUT_REJECTED error body (docs/api-contracts.md) for the first error, else None."""
        if not self.errors:
            return None
        e = self.errors[0]
        return {
            "error": {
                "code": "INPUT_REJECTED",
                "message": message,
                "details": {"line": e.line, "reason": e.reason},
            }
        }


def decode_text(data: bytes | str) -> str:
    """UTF-8 (BOM ok) first, else charset-normalizer's best guess; ValueError if neither works."""
    if isinstance(data, str):
        return data.removeprefix("﻿")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        best = from_bytes(data).best()
        if best is None:
            raise ValueError("cannot detect text encoding") from None
        return str(best)


def fail(reason: str, line: int | None = None) -> Parsed[Any]:
    return Parsed(errors=[Issue(reason, line)])
