"""Parsers + validation: scripts, subtitles, bible, glossary, clearance log (deliverable 1.3)."""

from collections.abc import Callable
from typing import Any

from nip.ingest.bible import Bible, parse_bible
from nip.ingest.common import Issue, Parsed, decode_text
from nip.ingest.pdf import parse_pdf
from nip.ingest.script import Element, Scene, Script, parse_fdx, parse_fountain
from nip.ingest.subtitles import Cue, SubtitleTrack, parse_srt, parse_ttml, parse_vtt
from nip.ingest.tables import ClearanceEntry, GlossaryEntry, parse_clearance_log, parse_glossary

# source_file.format -> parser (docs/data-model.md)
PARSERS: dict[str, Callable[[bytes], Parsed[Any]]] = {
    "fountain": parse_fountain,
    "fdx": parse_fdx,
    "pdf": parse_pdf,
    "srt": parse_srt,
    "vtt": parse_vtt,
    "ttml": parse_ttml,
    "yaml": parse_bible,
}
# 'csv' is ambiguous: pick by source_file.kind
CSV_PARSERS: dict[str, Callable[[bytes], Parsed[Any]]] = {
    "glossary": parse_glossary,
    "clearance_log": parse_clearance_log,
}


def parse(fmt: str, data: bytes, kind: str | None = None) -> Parsed[Any]:
    """Parse + validate one source file by its `format` (and `kind`, for csv)."""
    fn = CSV_PARSERS[kind or ""] if fmt == "csv" else PARSERS[fmt]
    return fn(data)


__all__ = [
    "Bible",
    "ClearanceEntry",
    "Cue",
    "Element",
    "GlossaryEntry",
    "Issue",
    "Parsed",
    "Scene",
    "Script",
    "SubtitleTrack",
    "decode_text",
    "parse",
    "parse_bible",
    "parse_clearance_log",
    "parse_fdx",
    "parse_fountain",
    "parse_glossary",
    "parse_pdf",
    "parse_srt",
    "parse_ttml",
    "parse_vtt",
]
