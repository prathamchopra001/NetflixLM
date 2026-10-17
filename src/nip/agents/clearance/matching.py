"""Clearance matching (architecture.md > Agent 2 > Matching).

A detection (a typed candidate from `ocr_text`) is normalized and matched against the show's
clearance registry:

| status    | report treatment                                              |
|-----------|---------------------------------------------------------------|
| fictional | declared fictional in the bible: dropped, not a clearance item |
| cleared   | hidden from the report, kept for the audit trail               |
| pending / denied | high severity, always shown (never routed by confidence)  |
| unknown   | not in the log: severity by prominence                          |

Phones, plates, e-mails and URLs match exactly after normalization (a one-character difference is
another number, and a wrong "cleared" would hide it). Names (addresses, brands) match when their
tokens are contained in each other or `rapidfuzz.ratio >= threshold`, which absorbs OCR slips.
An item whose `scope` does not cover the episode does not apply: its text is unknown there.
When several in-scope items match, the strictest status wins (denied > pending > cleared).
A phone number or plate that is exactly one edit from a pending / denied one (and matches nothing
exactly) is a `near` match of that item and routes as it does (I3: an OCR slip never hides it).
"""

import re
from dataclasses import dataclass
from functools import cache
from typing import Any

import yaml
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from nip.config import config_dir

STATUSES = ("fictional", "cleared", "pending", "denied", "unknown")
_STRICT = {"denied": 3, "pending": 2, "cleared": 1}
NAME_CHECKS = ("clr.address", "clr.brand_text")
NEAR_CHECKS = (
    "clr.phone",
    "clr.plate",
)  # OCR slips of these must never hide a pending / denied item
MIN_NEAR_LEN = 6  # shorter identifiers are one edit from too many others


@cache
def _cfg() -> dict[str, Any]:
    cfg: dict[str, Any] = yaml.safe_load(
        (config_dir() / "clearance" / "matching.yaml").read_text("utf-8")
    )
    return cfg


@dataclass(frozen=True)
class Item:
    """One `clearance_item` row."""

    id: int
    name: str
    kind: str
    status: str
    scope: str | None = None


@dataclass(frozen=True)
class Registry:
    items: tuple[Item, ...] = ()
    fictional: tuple[str, ...] = ()  # names the bible declares fictional (any kind)


@dataclass(frozen=True)
class Match:
    status: str  # one of STATUSES
    item: Item | None = None  # the registry row behind cleared / pending / denied
    near: bool = False  # not an exact read: one character off a pending / denied identifier


def normalize(check: str, text: str) -> str:
    """The comparison form of a detected or registered value (case, punctuation, variants)."""
    if check == "clr.phone":
        digits = re.sub(r"\D", "", text)
        return digits[1:] if len(digits) == 11 and digits[0] == "1" else digits
    if check == "clr.url":
        t = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text.strip().casefold())
        return re.sub(r"^www\d?\.", "", t).rstrip("/.,;:")
    if check == "clr.email":
        return text.strip().casefold().rstrip(".,;:")
    if check == "clr.plate":
        return re.sub(r"[^0-9A-Z]", "", text.upper())
    cfg = _cfg()
    words = re.sub(r"[^\w]+", " ", text.casefold()).split()
    words = [cfg["abbreviations"].get(w, w) for w in words]
    while words and words[0] in cfg["leading_words"]:
        words = words[1:]
    while len(words) > 1 and words[-1] in cfg["legal_suffixes"]:
        words = words[:-1]
    return " ".join(words)


def _same_name(a: str, b: str, threshold: float) -> bool:
    """Equal, token-contained (one name inside the other) or within the fuzzy threshold."""
    if not a or not b:
        return False
    ta, tb = set(a.split()), set(b.split())
    if min(len(ta), len(tb)) >= 2 and (ta <= tb or tb <= ta):
        return True
    return a == b or fuzz.ratio(a, b) >= threshold


def _fictional(n: str, f: str, threshold: float) -> bool:
    """A detection is the bible's own name when it equals it (OCR slips allowed) or contains it as
    whole words ("SINTEL HAS" holds the film's title): what the production invented is not a
    clearance item."""
    return _same_name(n, f, threshold) or bool(f) and set(f.split()) <= set(n.split())


def _same(check: str, a: str, b: str, threshold: float) -> bool:
    if check in NAME_CHECKS:
        return _same_name(a, b, threshold)
    return bool(a) and a == b


def _parse_ep(ref: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"S(\d+)E(\d+)", ref.strip().upper())
    return (int(m[1]), int(m[2])) if m else None


def in_scope(scope: str | None, episode: str) -> bool:
    """`scope`: null (whole show), `S01E03`, a range `S01E01-S01E08`, or a comma list of both."""
    if not scope or not scope.strip():
        return True
    here = _parse_ep(episode)
    if here is None:
        return False
    for part in scope.split(","):
        lo, _, hi = part.partition("-")
        a, b = _parse_ep(lo), _parse_ep(hi or lo)
        if a is not None and b is not None and a <= here <= b:
            return True
    return False


def match(
    registry: Registry, check: str, text: str, episode: str, threshold: float = 90.0
) -> Match:
    """The registry status of one detection (`check`: its clr.* id, `episode`: S01E03)."""
    n = normalize(check, text)
    kinds = _cfg()["kinds"][check]
    hits = [
        i
        for i in registry.items
        if i.kind in kinds
        and in_scope(i.scope, episode)
        and _same(check, n, normalize(check, i.name), threshold)
    ]
    if hits:
        best = max(hits, key=lambda i: _STRICT.get(i.status, 0))
        return Match(best.status, best)
    if check in NEAR_CHECKS and len(n) >= MIN_NEAR_LEN:
        # An OCR misread (O/0, 1/I, a dropped digit) of a pending / denied phone number or plate
        # is a possible match of that item: it escalates like the item itself, never to hidden.
        # Exact matching stays the rule for "cleared": a wrong one would hide another number.
        close = [
            i
            for i in registry.items
            if i.kind in kinds
            and i.status in ("pending", "denied")
            and in_scope(i.scope, episode)
            and Levenshtein.distance(n, normalize(check, i.name)) <= 1
        ]
        if close:
            best = max(close, key=lambda i: _STRICT[i.status])
            return Match(best.status, best, near=True)
    # What the bible declares fictional (and the show's own title) is not a clearance item, but
    # only after the log: an entry of the clearance log always wins over the junk rules (N1).
    if check in NAME_CHECKS and any(
        _fictional(n, normalize(check, f), threshold) for f in registry.fictional
    ):
        return Match("fictional")
    return Match("unknown")
