"""Glossary and clearance-log CSV readers (docs/data-model.md): missing required columns are errors,
unknown columns are warnings."""

import csv
import io
import re
from dataclasses import dataclass
from typing import Any

from nip.ingest.common import Issue, Parsed, decode_text

_LANG_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")  # BCP 47 shape, not a registry lookup
STATUSES = ("cleared", "pending", "denied")


@dataclass(frozen=True)
class GlossaryEntry:
    term: str
    lang: str
    approved_rendering: str
    notes: str = ""


@dataclass(frozen=True)
class ClearanceEntry:
    item: str
    kind: str
    status: str
    scope: str = ""  # '' = show-wide, else e.g. 'S01E03'
    notes: str = ""


def _rows(
    data: bytes | str, required: tuple[str, ...], optional: tuple[str, ...], p: Parsed[Any]
) -> list[tuple[int, dict[str, str]]]:
    """(line, row) pairs with whitespace-stripped values; problems go to `p`."""
    try:
        reader = csv.DictReader(io.StringIO(decode_text(data), newline=""))
        header = [h.strip().lower() for h in reader.fieldnames or []]
    except (ValueError, csv.Error) as e:
        p.errors.append(Issue(str(e)))
        return []
    if not header:
        p.errors.append(Issue("File is empty", 1))
        return []
    p.errors += [Issue(f"Missing required column '{c}'", 1) for c in required if c not in header]
    p.warnings += [f"Unknown column '{c}'" for c in header if c not in required + optional]
    reader.fieldnames = header
    out = []
    for row in reader:
        if None in row:
            p.errors.append(Issue("Row has more fields than the header", reader.line_num))
        out.append((reader.line_num, {k: (v or "").strip() for k, v in row.items() if k}))
    return [(n, r) for n, r in out if any(r.values())]


def parse_glossary(data: bytes | str) -> Parsed[list[GlossaryEntry]]:
    p: Parsed[list[GlossaryEntry]] = Parsed()
    out: list[GlossaryEntry] = []
    entries: dict[tuple[str, str], str] = {}
    for n, r in _rows(data, ("term", "lang", "approved_rendering"), ("notes",), p):
        for col in ("term", "lang", "approved_rendering"):
            if col in r and not r[col]:
                p.errors.append(Issue(f"Empty '{col}'", n))
        if r.get("lang") and not _LANG_RE.match(r["lang"]):
            p.errors.append(Issue(f"Invalid language tag '{r['lang']}'", n))
        key = (r.get("term", ""), r.get("lang", ""))
        if entries.setdefault(key, r.get("approved_rendering", "")) != r.get(
            "approved_rendering", ""
        ):
            p.warnings.append(
                f"line {n}: '{key[0]}' ({key[1]}) has conflicting approved renderings"
            )
        out.append(
            GlossaryEntry(
                r.get("term", ""),
                r.get("lang", ""),
                r.get("approved_rendering", ""),
                r.get("notes", ""),
            )
        )
    p.data = out if p.ok else None
    return p


def parse_clearance_log(data: bytes | str) -> Parsed[list[ClearanceEntry]]:
    p: Parsed[list[ClearanceEntry]] = Parsed()
    out: list[ClearanceEntry] = []
    seen: set[tuple[str, str]] = set()
    for n, r in _rows(data, ("item", "kind", "status"), ("scope", "notes"), p):
        for col in ("item", "kind", "status"):
            if col in r and not r[col]:
                p.errors.append(Issue(f"Empty '{col}'", n))
        status = r.get("status", "").lower()
        if status and status not in STATUSES:
            p.errors.append(
                Issue(f"Invalid status '{r['status']}' (expected one of {', '.join(STATUSES)})", n)
            )
        key = (r.get("item", "").lower(), r.get("scope", ""))
        if key in seen:
            p.warnings.append(f"line {n}: duplicate entry for '{r.get('item')}' (scope '{key[1]}')")
        seen.add(key)
        out.append(
            ClearanceEntry(
                r.get("item", ""), r.get("kind", ""), status, r.get("scope", ""), r.get("notes", "")
            )
        )
    p.data = out if p.ok else None
    return p
