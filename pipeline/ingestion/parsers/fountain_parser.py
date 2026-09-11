import re
from typing import Optional

from pipeline.ingestion.normalizer.episode_document import DialogueLine, SceneBlock

SCENE_HEADING_RE = re.compile(r"^(INT\.|EXT\.|\.)(.+)", re.IGNORECASE)
CHARACTER_RE = re.compile(r"^([A-Z][A-Z\s]{1,40})(\s*\(.*\))?$")


def parse_fountain(file_path: str) -> list[SceneBlock]:
    with open(file_path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    blocks: list[SceneBlock] = []
    current_block: Optional[SceneBlock] = None
    current_character: Optional[str] = None
    current_line_parts: list[str] = []
    current_stage_parts: list[str] = []
    scene_counter = 0
    i = 0

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

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            _flush_dialogue()
            i += 1
            continue

        if SCENE_HEADING_RE.match(stripped):
            _flush_block()
            scene_counter += 1
            heading = stripped.lstrip(".")
            current_block = SceneBlock(
                scene_id=f"SC{scene_counter:03d}",
                location=heading.strip(),
            )
            _parse_time_of_day(heading, current_block)

        elif current_block is not None and CHARACTER_RE.match(stripped):
            _flush_dialogue()
            name_match = CHARACTER_RE.match(stripped)
            if name_match:
                current_character = name_match.group(1).strip()

        elif current_character and current_block is not None:
            current_line_parts.append(stripped)

        elif current_block is not None:
            current_stage_parts.append(stripped)

        i += 1

    _flush_block()
    return blocks


def _parse_time_of_day(heading: str, block: SceneBlock) -> None:
    if not heading:
        return
    parts = heading.split("-")
    if len(parts) > 1:
        block.time_of_day = parts[-1].strip()
