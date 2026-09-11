from pathlib import Path

from pipeline.ingestion.parsers.fdx_parser import parse_fdx
from pipeline.ingestion.parsers.fountain_parser import parse_fountain
from pipeline.ingestion.parsers.pdf_parser import parse_pdf
from pipeline.ingestion.parsers.subtitle_parser import parse_subtitles
from pipeline.ingestion.normalizer.episode_document import SceneBlock, SubtitleSegment


def parse_script(file_path: str) -> list[SceneBlock]:
    ext = Path(file_path).suffix.lower()
    if ext == ".fdx":
        return parse_fdx(file_path)
    elif ext == ".pdf":
        return parse_pdf(file_path)
    elif ext in (".fountain", ".txt", ".fountain"):
        return parse_fountain(file_path)
    else:
        raise ValueError(f"Unsupported script format: {ext}")
