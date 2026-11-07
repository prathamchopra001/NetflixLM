"""Parsers + validation: scripts, subtitles, bible, glossary, clearance log (deliverable 1.3)."""

from collections.abc import Callable
from typing import Any

from nip.ingest.bible import Bible, parse_bible
from nip.ingest.common import Issue, Parsed, decode_text, fail
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
    """Parse + validate one source file by its `format` (and `kind`, for csv).

    ValueError for an unknown format/kind (a caller bug); anything a parser raises on hostile or
    corrupt input becomes a validation error, so the door never raises on file content.
    """
    fn = CSV_PARSERS.get(kind or "") if fmt == "csv" else PARSERS.get(fmt)
    if fn is None:
        raise ValueError(f"no parser for format {fmt!r}" + (f", kind {kind!r}" if kind else ""))
    try:
        return fn(data)
    except Exception as e:  # the parsers' promise: content problems are Issues, not exceptions
        return fail(f"cannot parse {fmt}: {type(e).__name__}: {e}")


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
