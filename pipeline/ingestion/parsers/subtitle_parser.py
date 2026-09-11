import re
from pathlib import Path

from pipeline.ingestion.normalizer.episode_document import SubtitleSegment

SRT_TIMESTAMP_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")
VTT_TIMESTAMP_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[.](\d{3})")
FPS = 24


def parse_subtitles(file_path: str) -> list[SubtitleSegment]:
    ext = Path(file_path).suffix.lower()
    if ext == ".srt":
        return parse_srt(file_path)
    elif ext == ".vtt":
        return parse_vtt(file_path)
    else:
        raise ValueError(f"Unsupported subtitle format: {ext}")


def parse_srt(file_path: str) -> list[SubtitleSegment]:
    with open(file_path, encoding="utf-8-sig") as f:
        content = f.read()
    return _parse_srt_content(content)


def parse_vtt(file_path: str) -> list[SubtitleSegment]:
    with open(file_path, encoding="utf-8-sig") as f:
        content = f.read()
    return _parse_vtt_content(content)


def _parse_srt_content(content: str) -> list[SubtitleSegment]:
    segments: list[SubtitleSegment] = []
    blocks = re.split(r"\n\s*\n", content.strip())

    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue

        ts_line = None
        for line in lines:
            if " --> " in line:
                ts_line = line
                break
        if not ts_line:
            continue

        start_tc, end_tc = _parse_srt_timestamps(ts_line)
        if start_tc is None or end_tc is None:
            continue

        text_lines: list[str] = []
        for line in lines:
            if " --> " in line:
                continue
            if re.match(r"^\d+$", line.strip()):
                continue
            text_lines.append(line.strip())

        text = " ".join(text_lines).strip()
        if not text:
            continue

        segments.append(SubtitleSegment(text=text, start_tc=start_tc, end_tc=end_tc))

    return segments


def _parse_vtt_content(content: str) -> list[SubtitleSegment]:
    segments: list[SubtitleSegment] = []
    lines = content.strip().splitlines()
    i = 0

    if lines and lines[0].startswith("WEBVTT"):
        i = 1

    while i < len(lines):
        line = lines[i].strip()
        if " --> " in line:
            start_tc, end_tc = _parse_vtt_timestamps(line)
            if start_tc is not None and end_tc is not None:
                i += 1
                text_lines: list[str] = []
                while i < len(lines) and lines[i].strip() and "--> " not in lines[i]:
                    text_lines.append(lines[i].strip())
                    i += 1
                text = " ".join(text_lines).strip()
                if text:
                    segments.append(
                        SubtitleSegment(text=text, start_tc=start_tc, end_tc=end_tc)
                    )
                continue
        i += 1

    return segments


def _ms_to_smpte(hours: str, minutes: str, seconds: str, millis: str) -> str:
    ms = int(millis)
    frames = round(ms * FPS / 1000)
    if frames >= FPS:
        frames = FPS - 1
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}:{frames:02d}"


def _parse_srt_timestamps(ts_line: str) -> tuple[str | None, str | None]:
    parts = ts_line.split("-->")
    if len(parts) != 2:
        return None, None

    start_m = SRT_TIMESTAMP_RE.search(parts[0])
    end_m = SRT_TIMESTAMP_RE.search(parts[1])
    if not start_m or not end_m:
        return None, None

    start_tc = _ms_to_smpte(*start_m.groups())
    end_tc = _ms_to_smpte(*end_m.groups())
    return start_tc, end_tc


def _parse_vtt_timestamps(ts_line: str) -> tuple[str | None, str | None]:
    parts = ts_line.split("-->")
    if len(parts) != 2:
        return None, None

    start_m = VTT_TIMESTAMP_RE.search(parts[0])
    end_m = VTT_TIMESTAMP_RE.search(parts[1])

    if start_m is None:
        start_m = SRT_TIMESTAMP_RE.search(parts[0])
    if end_m is None:
        end_m = SRT_TIMESTAMP_RE.search(parts[1])

    if not start_m or not end_m:
        return None, None

    start_tc = _ms_to_smpte(*start_m.groups())
    end_tc = _ms_to_smpte(*end_m.groups())
    return start_tc, end_tc
