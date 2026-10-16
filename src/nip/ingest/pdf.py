"""Text-based screenplay PDF reader: classifies each line by its indent (D-027)."""

import io
import re
from typing import Any

import pdfplumber

from nip.ingest.common import Parsed, fail
from nip.ingest.script import HEADING_RE, Raw, Script, build_script, speaker_name

_SKIP_RE = re.compile(
    r"^(\d+\.?|\(?(CONTINUED|MORE)\)?:?)$", re.IGNORECASE
)  # page numbers, CONTINUED/MORE
_TRANSITION_RE = re.compile(r"^([A-Z][A-Z .]*TO:|FADE (IN|OUT)[.:]?|CUT TO BLACK\.?)$")
_NUMBERED_RE = re.compile(
    r"^(?:(\d+[A-Z]?)\s+)?(.*?)(?:\s+\d+[A-Z]?)?$"
)  # '12 INT. HOUSE - DAY 12'
# Indent (pt) from the action margin; Courier 12 pt screenplays sit at roughly
# +72 dialogue, +115 parenthetical, +158 character.
_DIALOGUE, _PAREN, _CHARACTER, _TRANSITION = 36, 94, 137, 250


def _text_x0(ln: dict[str, Any]) -> float:
    """x0 of the line's text, skipping a scene number printed in the gutter before a heading."""
    m = _NUMBERED_RE.match(ln["text"].strip())
    if m and m.group(1) and HEADING_RE.match(m.group(2)):
        glyphs = [c for c in ln["chars"] if c["text"].strip()]
        return float(glyphs[len(m.group(1))]["x0"])
    return float(ln["x0"])


def parse_pdf(data: bytes) -> Parsed[Script]:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            lines = [ln for page in pdf.pages for ln in page.extract_text_lines()]
    except Exception as e:  # pdfminer raises many exception types on corrupt input
        return fail(f"Unreadable PDF: {e}")
    lines = [ln for ln in lines if not _SKIP_RE.match(ln["text"].strip())]
    if not lines:
        return fail("PDF has no extractable text (scanned or image-only?)")
    for ln in lines:
        ln["x0"] = _text_x0(ln)
    margin = min(ln["x0"] for ln in lines)  # action / heading margin
    items: list[Raw] = []
    speaker: str | None = None
    prev: tuple[str, float] | None = (
        None  # (kind, bottom) of the previous line, to join wrapped lines
    )
    for ln in lines:
        text, off = ln["text"].strip(), ln["x0"] - margin
        tag: str | None = None
        if off < _DIALOGUE:
            m = _NUMBERED_RE.match(text)
            if m and HEADING_RE.match(m.group(2)):
                kind, tag, text = "heading", m.group(1), m.group(2)
            else:
                kind = "transition" if _TRANSITION_RE.match(text) else "action"
        elif off < _PAREN:
            kind, tag = "dialogue", speaker
        elif off < _CHARACTER:
            kind, tag, text = "parenthetical", speaker, text.removeprefix("(").removesuffix(")")
        elif off < _TRANSITION and not _TRANSITION_RE.match(text):
            speaker, prev = speaker_name(text), None
            continue
        else:
            kind = "transition"
        if prev and prev[0] == kind and kind in ("action", "dialogue") and ln["top"] - prev[1] < 4:
            k, t, g = items[-1]
            items[-1] = (k, f"{t} {text}", g)
        else:
            items.append((kind, text, tag))
        prev = (kind, ln["bottom"])
    return build_script(items)
