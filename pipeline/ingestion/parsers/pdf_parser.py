import re
from typing import Optional

import pdfplumber

from pipeline.ingestion.normalizer.episode_document import DialogueLine, SceneBlock

SCENE_HEADING_RE = re.compile(r"^(INT\.|EXT\.)\s", re.IGNORECASE)
CHARACTER_RE = re.compile(r"^([A-Z][A-Z\s]{1,40})$")


def parse_pdf(file_path: str) -> list[SceneBlock]:
    text = _extract_text(file_path)
    return _split_into_blocks(text)


def _extract_text(file_path: str) -> str:
    pages: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)
    return "\n".join(pages)


def _split_into_blocks(text: str) -> list[SceneBlock]:
    lines = text.split("\n")
    blocks: list[SceneBlock] = []
    current_block: Optional[SceneBlock] = None
    current_character: Optional[str] = None
    current_line_parts: list[str] = []
    current_stage_parts: list[str] = []
    scene_counter = 0

    def _flush_dialogue() -> None:
        nonlocal current_character, current_line_parts
        if current_character and current_line_parts and current_block is not None:
            current_block.dialogue.append(
                DialogueLine(
                    character=current_character,
                    line=" ".join(current_line_parts).strip(),
                )
            )
            if current_character.upper() not in current_block.characters_present:
                current_block.characters_present.append(current_character.upper())
        current_character = None
        current_line_parts = []

    def _flush_block() -> None:
        nonlocal current_block, current_stage_parts
        _flush_dialogue()
        if current_block is not None:
            if current_stage_parts:
                current_block.stage_directions = " ".join(current_stage_parts).strip()
            blocks.append(current_block)
        current_block = None
        current_stage_parts = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if SCENE_HEADING_RE.match(stripped):
            _flush_block()
            scene_counter += 1
            current_block = SceneBlock(
                scene_id=f"SC{scene_counter:03d}",
                location=stripped,
            )
            _parse_time_of_day(stripped, current_block)

        elif CHARACTER_RE.match(stripped) and current_block is not None:
            _flush_dialogue()
            current_character = stripped.strip()

        elif current_character and current_block is not None:
            current_line_parts.append(stripped)

        elif current_block is not None:
            current_stage_parts.append(stripped)

    _flush_block()
    return blocks


def _parse_time_of_day(heading: str, block: SceneBlock) -> None:
    if not heading:
        return
    parts = heading.split("-")
    if len(parts) > 1:
        block.time_of_day = parts[-1].strip()
