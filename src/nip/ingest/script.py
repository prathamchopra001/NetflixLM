"""Script readers -> scenes of dialogue/action/parenthetical/transition lines (data-model.md).

Fountain goes through screenplay-tools; FDX is our own reader because screenplay-tools drops all but
the first text run of a paragraph (D-027).
"""

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Literal

from screenplay_tools.fountain.parser import Parser as FountainParser
from screenplay_tools.screenplay import ElementType

from nip.ingest.common import Parsed, decode_text, fail

Kind = Literal["dialogue", "action", "parenthetical", "transition"]
_EMPHASIS_RE = re.compile(r"(\*{1,3}|(?<!\w)_)(?=\S)(.+?)(?<=\S)\1(?!\w)")
HEADING_RE = re.compile(r"^\s*(INT|EXT|EST|INT\./EXT|INT/EXT|I/E)(\.|\s)", re.IGNORECASE)


@dataclass(frozen=True)
class Element:
    kind: Kind
    text: str
    speaker: str | None = None  # dialogue / parenthetical only
    extension: str | None = None  # the cue's extension as written: "(V.O.)", "(O.S.) (CONT'D)"


@dataclass
class Scene:
    number: str  # script_scene_no: '12', '12A'; sequential '1', '2', ... when the script has none
    heading: str
    elements: list[Element] = field(default_factory=list)

    @property
    def time_of_day(self) -> str | None:
        _, sep, tail = self.heading.rpartition(" - ")
        return (tail.strip() or None) if sep and HEADING_RE.match(self.heading) else None

    @property
    def text_hash(self) -> str:
        """sha256 over heading + element text; drives incremental re-runs."""
        return hashlib.sha256(
            "\n".join([self.heading, *(e.text for e in self.elements)]).encode()
        ).hexdigest()


@dataclass
class Script:
    title: str | None
    scenes: list[Scene]


# (kind, text, tag): "heading" (tag = explicit scene no.) or an Element kind (tag = the character
# cue as written, e.g. "MAYA (V.O.)": build_script splits it into speaker and extension)
Raw = tuple[str, str, str | None]


def build_script(items: list[Raw], title: str | None = None) -> Parsed[Script]:
    scenes: list[Scene] = []
    warnings: list[str] = []
    dropped = 0
    for kind, text, tag in items:
        text = text.strip()
        if kind == "heading":
            scenes.append(Scene(tag or str(len(scenes) + 1), text))
        elif not text:
            continue
        elif scenes:
            who = (speaker_name(tag), cue_extension(tag)) if tag else (None, None)
            scenes[-1].elements.append(Element(kind, text, *who))  # type: ignore[arg-type]
        else:
            dropped += 1
    if not scenes:
        return fail("Script has no scene headings")
    if dropped:
        warnings.append(f"{dropped} element(s) before the first scene heading were ignored")
    seen: set[str] = set()
    for s in scenes:
        if s.number in seen:
            warnings.append(f"Duplicate scene number {s.number}")
        seen.add(s.number)
    return Parsed(Script(title, scenes), warnings=warnings)


def parse_fountain(data: bytes | str) -> Parsed[Script]:
    text = re.sub(r"/\*.*?\*/", "", decode_text(data), flags=re.DOTALL)  # lib mishandles boneyards
    text = _EMPHASIS_RE.sub(r"\2", text)  # *bold*, **bold**, _underline_
    p = FountainParser()
    p.add_text(text)
    items: list[Raw] = []
    speaker: str | None = None
    for e in p.script.elements:
        t = e.type
        if t == ElementType.HEADING:
            if e.forced or HEADING_RE.match(e.text):
                items.append(("heading", e.text, e.scene_number))
            else:  # the lib calls "FADE IN:" a heading
                items.append(("transition", e.text, None))
        elif t == ElementType.CHARACTER:  # the lib splits the cue; keep its extension
            speaker = f"{e.name} ({e.extension})" if e.extension else e.name
        elif t in (ElementType.DIALOGUE, ElementType.LYRIC):
            items.append(("dialogue", e.text, speaker))
        elif t == ElementType.PARENTHETICAL:
            items.append(("parenthetical", e.text, speaker))
        elif t == ElementType.TRANSITION:
            items.append(("transition", e.text, None))
        elif t == ElementType.ACTION:
            items.append(("action", e.text, None))
    title = next((x.text for x in p.script.titleEntries if x.key.lower() == "title"), None)
    return build_script(items, title)


_EXTENSION_RE = re.compile(r"(?:\s*\([^)]*\))+\s*$")


def speaker_name(character_line: str) -> str:
    """'MAYA (V.O.)' -> 'MAYA'; 'MAYA (V.O.) (CONT'D)' -> 'MAYA'."""
    return _EXTENSION_RE.sub("", character_line.strip())


def cue_extension(character_line: str) -> str | None:
    """'MAYA (V.O.)' -> '(V.O.)'; None without one (2.1B: off-screen voices get no presence)."""
    m = _EXTENSION_RE.search(character_line.strip())
    return m.group().strip() if m else None


_FDX_KINDS: dict[str, str] = {
    "Action": "action",
    "General": "action",
    "Dialogue": "dialogue",
    "Parenthetical": "parenthetical",
    "Transition": "transition",
}


def parse_fdx(data: bytes | str) -> Parsed[Script]:
    try:
        root = ET.fromstring(data.encode() if isinstance(data, str) else data)
    except ET.ParseError as e:
        return fail(f"Malformed FDX XML: {e}", e.position[0])
    if root.tag != "FinalDraft":
        return fail("Not a Final Draft document (root element is not FinalDraft)", 1)
    items: list[Raw] = []
    speaker: str | None = None
    for p in root.iter("Paragraph"):  # iter() also reaches paragraphs inside <DualDialogue>
        ptype = p.get("Type", "Action")
        text = "".join(
            t for el in p.findall("Text") for t in el.itertext()
        )  # every run, not just the first
        if ptype.startswith("Scene Heading") or ptype == "Shot":
            items.append(("heading", text, p.get("Number") or None))
        elif ptype == "Character":
            speaker = text.strip()  # the whole cue: build_script splits off the extension
        elif ptype == "Parenthetical":
            items.append(
                ("parenthetical", text.strip().removeprefix("(").removesuffix(")"), speaker)
            )
        elif ptype == "Dialogue":
            items.append(("dialogue", text, speaker))
        else:
            items.append((_FDX_KINDS.get(ptype, "action"), text, None))
    return build_script(items)
