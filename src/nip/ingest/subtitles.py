"""SRT / WebVTT (pysubs2) and TTML / IMSC (ttconv) readers: cues with integer-millisecond times.

Cue times stay in ms; frame conversion (data-model.md, Subtitle conversion) belongs to nip.timecode.
TTML's declared frame rate is recorded on the track (None for SRT / VTT).
"""

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from fractions import Fraction

import pysubs2
from ttconv import model as tt_model
from ttconv.imsc import reader as imsc_reader
from ttconv.imsc.attributes import FrameRateAttribute

from nip.ingest.common import Issue, Parsed, decode_text, fail


@dataclass(frozen=True)
class Cue:
    idx: int  # 1-based position in the file (pysubs2 does not keep the numbers written in an SRT)
    start_ms: int
    end_ms: int
    text: str  # lines joined with '\n', markup removed
    line: int | None = None  # 1-based source line of the timing line (SRT / VTT)


@dataclass
class SubtitleTrack:
    cues: list[Cue]
    frame_rate: Fraction | None = None  # declared ttp:frameRate (TTML); None for SRT / VTT


_TS = r"(?:\d+:)?\d{1,2}:\d{2}[,.]\d{1,3}"
_TIMING = re.compile(rf"^\s*{_TS}\s*-->\s*{_TS}")
_TIMINGISH = re.compile(
    r"-+>|^\s*\d+:\d{2}[:,.]\d"
)  # looks like a timing line, so must match _TIMING


def _check_cues(cues: list[Cue], p: Parsed[SubtitleTrack]) -> None:
    for c in cues:
        where = f"cue {c.idx}"
        if c.end_ms <= c.start_ms:
            p.errors.append(
                Issue(f"{where}: end {c.end_ms} ms is not after start {c.start_ms} ms", c.line)
            )
        if not c.text.strip():
            p.warnings.append(f"{where}: empty text")
    for a, b in zip(cues, cues[1:], strict=False):
        if b.start_ms < a.start_ms:
            p.warnings.append(f"cue {b.idx}: starts before cue {a.idx}")
    if not cues:
        p.errors.append(Issue("Subtitle file has no cues"))


def _parse_pysubs2(data: bytes | str, fmt: str) -> Parsed[SubtitleTrack]:
    try:
        text = decode_text(data)
    except ValueError as e:
        return fail(str(e))
    p: Parsed[SubtitleTrack] = Parsed()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines()
    if fmt == "vtt" and not (lines and lines[0].startswith("WEBVTT")):
        return fail("Missing WEBVTT header", 1)
    timing_lines: list[int] = []
    for n, ln in enumerate(lines, 1):
        if _TIMING.match(ln):
            timing_lines.append(n)
        elif _TIMINGISH.search(ln):
            p.errors.append(Issue(f"Malformed cue timing: {ln.strip()!r}", n))
    try:
        events = list(pysubs2.SSAFile.from_string(text, format_=fmt))
    except Exception as e:  # pysubs2 raises on some bad timestamps
        return fail(f"Cannot parse {fmt.upper()}: {e}")
    if not p.errors and len(events) != len(timing_lines):
        p.errors.append(Issue(f"{len(timing_lines) - len(events)} cue(s) could not be parsed"))
    mapped = len(events) == len(timing_lines)
    cues = [
        Cue(i, e.start, e.end, e.plaintext.strip(), timing_lines[i - 1] if mapped else None)
        for i, e in enumerate(events, 1)
    ]
    _check_cues(cues, p)
    p.data = SubtitleTrack(cues)
    return p


def parse_srt(data: bytes | str) -> Parsed[SubtitleTrack]:
    return _parse_pysubs2(data, "srt")


def parse_vtt(data: bytes | str) -> Parsed[SubtitleTrack]:
    return _parse_pysubs2(data, "vtt")


def _ttml_text(e: tt_model.ContentElement) -> str:
    if isinstance(e, tt_model.Text):
        return str(e.get_text())
    if isinstance(e, tt_model.Br):
        return "\n"
    return "".join(_ttml_text(c) for c in e)


def _ttml_cues(
    e: tt_model.ContentElement,
    base: Fraction,
    out: list[tuple[Fraction | None, Fraction | None, str]],
) -> None:
    b = e.get_begin()
    if isinstance(e, tt_model.P):
        end = e.get_end()
        out.append(
            (None if b is None else base + b, None if end is None else base + end, _ttml_text(e))
        )
        return
    base += b or 0
    for c in e:
        _ttml_cues(c, base, out)


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.ERROR)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _ms(t: Fraction) -> int:
    return round(t * 1000)


def parse_ttml(data: bytes | str) -> Parsed[SubtitleTrack]:
    raw = data.encode() if isinstance(data, str) else data
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        return fail(f"Malformed TTML XML: {e}", e.position[0])
    cap = _Capture()
    log = logging.getLogger("ttconv")
    log.addHandler(cap)  # ttconv only logs bad timing expressions; they become validation errors
    try:
        doc = imsc_reader.to_model(ET.ElementTree(root))
    finally:
        log.removeHandler(cap)
    p: Parsed[SubtitleTrack] = Parsed(errors=[Issue(f"ttconv: {m}") for m in cap.messages])
    body = doc.get_body() if doc else None
    if body is None:
        p.errors.append(Issue("TTML has no body"))
        return p
    found: list[tuple[Fraction | None, Fraction | None, str]] = []
    _ttml_cues(body, Fraction(0), found)
    cues: list[Cue] = []
    for i, (begin, end, text) in enumerate(found, 1):
        if begin is None or end is None:
            p.errors.append(Issue(f"cue {i}: missing or invalid begin/end"))
            continue
        cues.append(
            Cue(i, _ms(begin), _ms(end), "\n".join(s.strip() for s in text.strip().split("\n")))
        )
    _check_cues(cues, p)
    declared = (
        FrameRateAttribute.extract(root)
        if FrameRateAttribute.frame_rate_qn in root.attrib
        else None
    )
    p.data = SubtitleTrack(cues, declared)
    return p
