"""Grounding validator (D-005, architecture.md › Timed facts): an event's quote must be in the
line it cites. Both are normalized (NFKC, typographic quote marks and dashes, whitespace), then
rapidfuzz `partial_ratio` (best-matching substring of the line) must reach the threshold
(EXP-006). A quote longer than its line is scored with plain `ratio`, so a fabricated quote that
merely contains the whole line does not pass. Events that fail are dropped and counted.
"""

import re
import unicodedata

from rapidfuzz import fuzz

THRESHOLD = 90.0  # proposed pipeline.yaml key knowledge.grounding.threshold; EXP-006 sets it
_MARKS = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'", "“": '"', "”": '"',
                        "„": '"', "‟": '"', "«": '"', "»": '"', "–": "-", "—": "-"})  # fmt: skip


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s).translate(_MARKS)).strip()


def score(quote: str, line: str) -> float:
    q, t = normalize(quote), normalize(line)
    if not q:
        return 0.0
    return fuzz.partial_ratio(q, t) if len(q) <= len(t) else fuzz.ratio(q, t)


def grounded(quote: str, line: str, threshold: float = THRESHOLD) -> bool:
    return score(quote, line) >= threshold
