from dataclasses import dataclass, field
from typing import List, Optional

from lxml import etree

from pipeline.ingestion.normalizer.episode_document import DialogueLine, SceneBlock


def parse_fdx(file_path: str) -> list[SceneBlock]:
    tree = etree.parse(file_path)
    root = tree.getroot()
    content = root.find("Content")
    if content is None:
        raise ValueError(f"No Content element found in FDX file: {file_path}")

    blocks: list[SceneBlock] = []
    scene_counter = 0
    current_block: Optional[SceneBlock] = None
    current_character: Optional[str] = None
    current_direction: str = ""
    current_lines: list[str] = []

    def _flush_dialogue() -> None:
        nonlocal current_character, current_direction, current_lines
        if current_character and current_lines and current_block is not None:
            current_block.dialogue.append(
                DialogueLine(
                    character=current_character,
                    line=" ".join(current_lines).strip(),
                    direction=current_direction.strip(),
                )
            )
            name_upper = current_character.upper()
            if name_upper not in current_block.characters_present:
                current_block.characters_present.append(name_upper)
        current_character = None
        current_direction = ""
        current_lines = []

    def _flush_block() -> None:
        nonlocal current_block
        _flush_dialogue()
        if current_block is not None:
            blocks.append(current_block)
        current_block = None

    for paragraph in content.iter("Paragraph"):
        para_type = paragraph.get("Type", "").strip()

        if para_type == "Scene Heading":
            _flush_block()
            scene_counter += 1
            heading = _extract_text(paragraph)
            current_block = SceneBlock(
                scene_id=f"SC{scene_counter:03d}",
                location=heading.strip(),
            )
            _parse_time_of_day(heading, current_block)

        elif para_type == "Character":
            _flush_dialogue()
            current_character = _extract_text(paragraph).strip()
            current_direction = ""

        elif para_type == "Parenetical":
            current_direction = _extract_text(paragraph).strip()

        elif para_type == "Dialogue":
            line = _extract_text(paragraph).strip()
            if line and current_character is not None:
                current_lines.append(line)

        elif para_type == "Action":
            action_text = _extract_text(paragraph).strip()
            if current_block is not None and action_text:
                if current_block.stage_directions:
                    current_block.stage_directions += " " + action_text
                else:
                    current_block.stage_directions = action_text

    _flush_block()
    return blocks


def _extract_text(paragraph) -> str:
    parts: list[str] = []
    for text_elem in paragraph.iter("Text"):
        if text_elem.text:
            parts.append(text_elem.text)
        if text_elem.tail:
            parts.append(text_elem.tail)
    return "".join(parts)


def _parse_time_of_day(heading: str, block: SceneBlock) -> None:
    if not heading:
        return
    parts = heading.split("-")
    if len(parts) > 1:
        block.time_of_day = parts[-1].strip()
