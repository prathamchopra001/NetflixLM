"""The synthetic show as data: scenes of lines, each line carrying its ground-truth facts.

`truth.json` is this model dumped (plus computed refs and setup/payoff pairs); the Fountain scripts
and the bible are rendered from it, and the plot injectors edit the model and render again, so the
truth of an injected show is exact by construction.
"""

import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from nip.contracts import refs


class Fact(BaseModel):
    """One fact the line states. Predicates: present_at, learns, references, holds (value.event is
    obtain or use), state (value.state is dead or destroyed), setup, payoff."""

    predicate: str
    subject: str  # entity id
    quote: str  # a substring of the line's text
    object: str | None = None
    value: dict[str, Any] | None = None


class Mention(BaseModel):
    surface: str  # exactly as it appears in the line text
    entity: str
    kind: Literal["name", "nickname", "description"]


class Line(BaseModel):
    kind: Literal["action", "dialogue"]
    text: str
    speaker: str | None = None  # entity id, dialogue only
    facts: list[Fact] = []
    mentions: list[Mention] = []


class Scene(BaseModel):
    no: str
    heading: str
    location: str  # entity id
    marker: Literal["flashback", "same_time"] | None = None
    story_day: int
    story_seq: int  # chronological rank; same-time scenes share one
    lines: list[Line]


class Entity(BaseModel):
    id: str
    kind: str  # character | location | prop | secret | org | brand
    name: str
    aliases: list[tuple[str, str]] = []  # (alias, nickname | description)
    attrs: dict[str, str] = {}  # character: gender, identity_hidden_until; secret: description...


class Show(BaseModel):
    show: str  # slug, as in bible.yaml
    title: str
    seed: int
    entities: list[Entity]
    episodes: dict[str, list[Scene]]
    touched: list[str] = []  # scene refs that injectors already edited

    def entity(self, id_: str) -> Entity:
        return next(e for e in self.entities if e.id == id_)

    def cast(self, scene: Scene) -> set[str]:
        return {f.subject for ln in scene.lines for f in ln.facts if f.predicate == "present_at"}


def merge_actions(lines: list[Line]) -> list[Line]:
    """Consecutive action paragraphs become one element when the script is read back (the Fountain
    reader joins them), so the model keeps them as one line: text joined by a blank line."""
    out: list[Line] = []
    for ln in lines:
        if out and ln.kind == "action" and out[-1].kind == "action":
            p = out[-1]
            joined = p.text + chr(10) * 2 + ln.text
            out[-1] = Line(
                kind="action",
                text=joined,
                facts=p.facts + ln.facts,
                mentions=p.mentions + ln.mentions,
            )
        else:
            out.append(ln)
    return out


def line_ref(ep: str, scene_no: str, seq: int) -> str:
    """`{ep}/line/{scene}.{seq}` (data-model.md > Evidence Refs); seq is the 1-based position of
    the element in the scene (the Fountain reader's `Scene.elements`)."""
    return f"{ep}/line/{scene_no}.{seq}"


def speaker_label(show: Show, entity_id: str) -> str:
    return show.entity(entity_id).name.split()[0].upper()


def render_fountain(show: Show, ep: str) -> str:
    """One episode as Fountain: title page, then slugline / action / character+dialogue blocks."""
    out = [f"Title: {show.title} {ep}", ""]
    for sc in show.episodes[ep]:
        out += [sc.heading, ""]
        for ln in sc.lines:
            if ln.kind == "dialogue":
                assert ln.speaker
                out += [speaker_label(show, ln.speaker), ln.text, ""]
            else:
                out += [ln.text, ""]
    return "\n".join(out)


def _first_learned(show: Show, secret: str) -> str | None:
    for ep, scenes in show.episodes.items():
        for sc in scenes:
            if any(
                f.predicate == "learns" and f.object == secret for ln in sc.lines for f in ln.facts
            ):
                return ep
    return None


def render_bible(show: Show) -> str:
    """`bible.yaml` (data-model.md > Show bible) from the entities and flashback markers."""
    chars = [e for e in show.entities if e.kind == "character"]
    secrets = [e for e in show.entities if e.kind == "secret"]
    fic = {k: [e.name for e in show.entities if e.kind == k] for k in ("brand", "org", "location")}
    data: dict[str, Any] = {
        "show": show.show,
        "characters": [
            {
                "id": c.id,
                "name": c.name,
                "aliases": [a for a, _ in c.aliases],
                "gender": c.attrs["gender"],
                "pronouns": {"en": "she/her" if c.attrs["gender"] == "female" else "he/him"},
                **(
                    {"identity_hidden_until": c.attrs["identity_hidden_until"]}
                    if "identity_hidden_until" in c.attrs
                    else {}
                ),
            }
            for c in chars
        ],
        "relationships": [
            {
                "between": [chars[0].id, chars[1].id],
                "timeline": [
                    {"from": "S01E01", "kind": "strangers"},
                    {"from": "S01E03", "kind": "partners", "register": {"es": "T", "fr": "T"}},
                ],
            }
        ],
        "secrets": [
            {
                "id": s.id,
                "description": s.attrs["description"],
                **({"revealed_on_screen": ep} if (ep := _first_learned(show, s.id)) else {}),
            }
            for s in secrets
        ],
        "fictional": {"brands": fic["brand"], "orgs": fic["org"], "places": fic["location"]},
        "story_overrides": [
            {"scene": refs.scene(ep, sc.no), "markers": ["flashback"], "story_day": sc.story_day}
            for ep, scenes in show.episodes.items()
            for sc in scenes
            if sc.marker == "flashback"
        ],
    }
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def setups(show: Show) -> list[dict[str, str]]:
    """Setup/payoff pairs from the facts: {entity, setup: line ref, payoff: line ref}."""
    seen: dict[str, dict[str, str]] = {}
    for ep, scenes in show.episodes.items():
        for sc in scenes:
            for seq, ln in enumerate(sc.lines, 1):
                for f in ln.facts:
                    if f.predicate in ("setup", "payoff"):
                        seen.setdefault(f.subject, {"entity": f.subject})[f.predicate] = line_ref(
                            ep, sc.no, seq
                        )
    return [v for v in seen.values() if "setup" in v and "payoff" in v]


def truth(show: Show) -> dict[str, Any]:
    """The `truth.json` object: the model plus every scene/line ref and the setup/payoff pairs."""
    d = show.model_dump(mode="json")
    for ep, scenes in d["episodes"].items():
        for sc in scenes:
            sc["ref"] = refs.scene(ep, sc["no"])
            for seq, ln in enumerate(sc["lines"], 1):
                ln["ref"] = line_ref(ep, sc["no"], seq)
    d["setups"] = setups(show)
    return d


def write_show(show: Show, out: Path) -> None:
    """`S01E0n.fountain`, `bible.yaml`, `truth.json` under `out`."""
    out.mkdir(parents=True, exist_ok=True)
    for ep in show.episodes:
        (out / f"{ep}.fountain").write_text(
            render_fountain(show, ep), encoding="utf-8", newline="\n"
        )
    (out / "bible.yaml").write_text(render_bible(show), encoding="utf-8", newline="\n")
    (out / "truth.json").write_text(
        json.dumps(truth(show), indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def read_show(path: Path) -> Show:
    """A show dir (or its truth.json) back into the model; computed fields are ignored."""
    f = path / "truth.json" if path.is_dir() else path
    return Show.model_validate_json(f.read_text(encoding="utf-8"))
