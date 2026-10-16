"""Stage 3 fact extraction (architecture.md › Timed facts, D-025): one LLM unit per scene.

The model reads one scene (lines numbered by `seq`, dialogue as `SPEAKER: text`) plus the registry
and the bible entries of the characters present, and returns events in a fixed JSON schema:
predicate, subject, object, value, line, quote, confidence. Subject and object are registry keys
as an enum plus `UNKNOWN` (D-025); `enum=False` is EXP-020's free-text arm (names, resolved
afterwards). A line number outside the scene is a structural error (one instructor repair); a bad
quote is not: the grounding validator drops it afterwards, so the raw events are kept per run
(`runs/{run_id}/{ep}/knowledge.events.raw.jsonl`) and EXP-006 re-thresholds without new calls.

Registry keys: the bible id for characters, the canonical name otherwise (secret ids, place,
brand, org and term names). Candidates are not in the enum (their names change between runs, and
with them every later prompt); `UNKNOWN` names are matched against their aliases (`entities`).
"""

import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from string import Template
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, Field, ValidationInfo, create_model
from sqlalchemy import Connection, delete, insert, select, update

from nip.config import config_dir, pipeline_config
from nip.contracts.fact import Predicate
from nip.contracts.plan import Slot
from nip.knowledge.entities import Resolver
from nip.knowledge.grounding import THRESHOLD, grounded
from nip.runtime.clients import LLMClient, StubLLM
from nip.store import schema

log = logging.getLogger(__name__)

STAGE = "knowledge.extract"
_CFG = pipeline_config()["knowledge"]["extract"]
PROMPT_VERSION: str = _CFG["prompt_version"]
MAX_TOKENS = int(_CFG["max_tokens"])
UNKNOWN = "UNKNOWN"
IDS_RULE = {
    True: "`subject` and `object` are registry keys (the first word of a registry line). For"
    " someone or something that is not in the registry, use `UNKNOWN` and write its name as the"
    " scene gives it in `subject_name` / `object_name`. Leave `object` out when the predicate"
    " has none.",
    False: "`subject` and `object` are names exactly as the scene gives them (for the speaker, the"
    " speaker's name). Leave `object` out when the predicate has none, and leave `subject_name`"
    " and `object_name` out.",
}
# value text -> fact_event.value: the head goes under this key, "head: detail" adds "detail"
VALUE_KEY = {"state": "state", "holds": "event", "owns": "event", "wearing": "event",
             "relationship": "kind", "setup": "importance"}  # fmt: skip


@dataclass(frozen=True)
class Line:
    seq: int  # 1-based in the scene, as script_line.seq and `{ep}/line/{scene}.{seq}`
    kind: str
    text: str
    speaker: str | None = None
    id: int | None = None  # script_line.id


@dataclass(frozen=True)
class SceneText:
    ref: str  # `{ep}/sc/{no}`
    heading: str
    lines: list[Line]
    id: int | None = None  # scene.id


@dataclass(frozen=True)
class Entry:
    key: str
    kind: str
    name: str
    aliases: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)  # bible attributes


def _line_in_scene(v: int, info: ValidationInfo) -> int:
    seqs = (info.context or {}).get("lines")
    if seqs is not None and v not in seqs:
        raise ValueError(f"line {v} is not a line of this scene ({sorted(seqs)})")
    return v


def event_schema(keys: Sequence[str] | None) -> type[BaseModel]:
    """`Extraction{events: [Event]}`; subject/object an enum of `keys` + UNKNOWN, or free text."""
    ref: Any = Literal[(*keys, UNKNOWN)] if keys is not None else str
    event = create_model(
        "Event",
        line=(Annotated[int, AfterValidator(_line_in_scene)], ...),
        quote=(str, ...),
        predicate=(Predicate, ...),
        subject=(ref, ...),
        subject_name=(str | None, None),
        object=(ref | None, None),
        object_name=(str | None, None),
        value=(str | None, None),
        confidence=(float, Field(ge=0, le=1)),
    )
    return create_model("Extraction", events=(list[event], ...))


def _present(scene: SceneText, registry: Sequence[Entry]) -> list[Entry]:
    text = " ".join([scene.heading, *(f"{ln.speaker or ''} {ln.text}" for ln in scene.lines)])

    def named(n: str) -> bool:
        return re.search(rf"(?<!\w){re.escape(n)}(?!\w)", text, re.IGNORECASE) is not None

    return [
        e
        for e in registry
        if e.kind == "character" and any(map(named, (e.name, e.name.split()[0], *e.aliases)))
    ]


def render(scene: SceneText, registry: Sequence[Entry], enum: bool = True) -> str:
    def reg(e: Entry) -> str:
        name = e.details.get("description", e.name) if e.kind == "secret" else e.name
        also = f"; also: {', '.join(e.aliases)}" if e.aliases else ""
        return f"- {e.key} ({e.kind}): {name}{also}"

    def bible(e: Entry) -> str:
        d = e.details
        bits = [d.get("gender"), *(d.get("pronouns") or {}).values()]
        if d.get("identity_hidden_until"):
            bits.append(f"identity hidden from the viewer until {d['identity_hidden_until']}")
        return f"- {e.key}: {e.name}; " + ", ".join(str(b) for b in bits if b)

    def line(ln: Line) -> str:
        who = f"{ln.speaker}: " if ln.kind == "dialogue" and ln.speaker else f"({ln.kind}) "
        return f"[{ln.seq}] {who}{ln.text}"

    tpl = Template((config_dir() / "prompts" / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8"))
    return tpl.substitute(
        ids_rule=IDS_RULE[enum],
        registry="\n".join(map(reg, registry)) or "(empty)",
        bible="\n".join(map(bible, _present(scene, registry))) or "(none from the bible)",
        scene="\n".join([scene.heading, *map(line, scene.lines)]),
    )


def extract_scene(
    llm: LLMClient | StubLLM, scene: SceneText, registry: Sequence[Entry], enum: bool = True
) -> list[dict[str, Any]]:
    """Raw (pre-grounding) events of one scene: the model's events plus `scene` (the ref)."""
    out = llm.complete(
        render(scene, registry, enum),
        event_schema([e.key for e in registry] if enum else None),
        max_tokens=MAX_TOKENS,
        context={"lines": {ln.seq for ln in scene.lines}},
    )
    return [{"scene": scene.ref, **e.model_dump(mode="json")} for e in out.events]  # type: ignore[attr-defined]


def value_json(predicate: str, value: str | None) -> dict[str, Any] | None:
    """`"injured: left hand cut"` -> {"state": "injured", "detail": "left hand cut"}; the head of
    a setup's value is its importance (int); other predicates keep the text under "detail"."""
    if not value or not value.strip():
        return None
    head, _, detail = (s.strip() for s in value.partition(":"))
    key = VALUE_KEY.get(predicate, "detail")
    out: dict[str, Any] = {key: int(head) if key == "importance" and head.isdigit() else head}
    return out | ({"detail": detail} if detail else {})


# ---- store -------------------------------------------------------------------------------------


def load_registry(conn: Connection, show_id: int) -> list[Entry]:
    """Confirmed entities of the show (bible, glossary), in id order, with their aliases."""
    e, a = schema.entity, schema.entity_alias
    aliases: dict[int, list[str]] = {}
    for eid, alias in conn.execute(
        select(a.c.entity_id, a.c.alias)
        .join(e)
        .where(e.c.show_id == show_id, a.c.kind.in_(("name", "nickname")))
        .order_by(a.c.alias)
    ):
        aliases.setdefault(eid, []).append(alias)
    out = []
    for r in conn.execute(
        select(e).where(e.c.show_id == show_id, e.c.status == "confirmed").order_by(e.c.id)
    ):
        key = r.attributes.get("bible_id") or r.canonical_name
        names = tuple(x for x in aliases.get(r.id, []) if x not in (r.canonical_name, key))
        out.append(Entry(key, r.kind, r.canonical_name, names, dict(r.attributes)))
    return out


def load_scenes(conn: Connection, episode: str, episode_id: int) -> list[SceneText]:
    """The episode's scenes and lines (speaker: `script_line.speaker`, as the script names it)."""
    sc, ln = schema.scene, schema.script_line
    rows = conn.execute(
        select(
            sc.c.id,
            sc.c.script_scene_no,
            sc.c.heading,
            ln.c.id.label("line_id"),
            ln.c.seq,
            ln.c.kind,
            ln.c.text,
            ln.c.speaker,
        )
        .join(ln, ln.c.scene_id == sc.c.id)
        .where(sc.c.episode_id == episode_id)
        .order_by(sc.c.id, ln.c.seq)
    ).all()
    scenes: dict[int, SceneText] = {}
    for r in rows:
        s = scenes.setdefault(
            r.id, SceneText(f"{episode}/sc/{r.script_scene_no}", r.heading, [], r.id)
        )
        s.lines.append(Line(r.seq, r.kind, r.text, r.speaker, r.line_id))
    return list(scenes.values())


def save_events(
    conn: Connection,
    show_id: int,
    scene: SceneText,
    raw: list[dict[str, Any]],
    threshold: float = THRESHOLD,
) -> tuple[int, int]:
    """Replace the scene's fact_event rows with the grounded, resolved `raw` events. Returns
    (kept, dropped: quote not grounded, or no subject name at all). Unresolved names become
    candidate entities (`Resolver`). Each raw event is annotated in place with `grounded` and,
    when grounded, the resolved `subject_id` / `object_id`."""
    fe = schema.fact_event
    conn.execute(delete(fe).where(fe.c.scene_id == scene.id))
    lines = {ln.seq: ln for ln in scene.lines}
    resolver = Resolver(conn, show_id)
    rows: list[dict[str, Any]] = []
    for ev in raw:
        ln = lines[ev["line"]]
        ev["grounded"] = grounded(ev["quote"], ln.text, threshold)
        if not ev["grounded"]:
            continue
        pred = ev["predicate"]
        ev["subject_id"] = resolver.resolve(ev["subject"], ev.get("subject_name"), pred, "subject")
        ev["object_id"] = resolver.resolve(ev.get("object"), ev.get("object_name"), pred, "object")
        if ev["subject_id"] is None:  # an empty name: nothing to resolve or create
            continue
        if ev["object_id"] is None and pred in ("holds", "owns", "wearing"):
            continue  # holding nothing: would merge with any other object-less holds (review M-8)
        rows.append(
            {
                "scene_id": scene.id,
                "line_id": ln.id,
                "predicate": pred,
                "subject_id": ev["subject_id"],
                "object_id": ev["object_id"],
                "value": value_json(pred, ev.get("value")),
                "quote": ev["quote"],
                "confidence": ev["confidence"],
            }
        )
    if rows:
        conn.execute(insert(fe), rows)
    return len(rows), len(raw) - len(rows)


def save_speakers(conn: Connection, show_id: int, scene: SceneText) -> None:
    """`script_line.speaker_entity_id` for dialogue lines whose speaker name matches one entity
    (2.3's plot.dead_acts reads it); unmatched speakers stay NULL (no candidate)."""
    resolver = Resolver(conn, show_id)
    ln = schema.script_line
    for line in scene.lines:
        if line.speaker and (eid := resolver.match(line.speaker)) is not None:
            conn.execute(update(ln).where(ln.c.id == line.id).values(speaker_entity_id=eid))


def text_llm(plan: Any) -> LLMClient | StubLLM:
    """The Plan's text_llm client; the stub when the Plan has no text_llm decision."""
    if Slot.TEXT_LLM not in plan.decisions:
        return StubLLM()
    from nip.runtime.catalog import load_catalog
    from nip.runtime.clients import llm

    return llm(plan, load_catalog(), Slot.TEXT_LLM)


def stage_extract(ep: Any) -> None:
    """Pipeline stage `knowledge.extract` (`fn(ep: EpisodeRun)`): one work unit per scene."""
    show_id = conn_show_id(ep.conn, ep.episode_id)
    client = text_llm(ep.plan)
    registry = load_registry(ep.conn, show_id)
    scenes = load_scenes(ep.conn, ep.episode, ep.episode_id)
    raw_all: list[dict[str, Any]] = []
    kept = dropped = 0
    for sc in scenes:
        with ep.unit(STAGE, sc.ref, model_variant=client.variant):
            raw = extract_scene(client, sc, registry)
            k, d = save_events(ep.conn, show_id, sc, raw)
            save_speakers(ep.conn, show_id, sc)
            raw_all += raw
            kept, dropped = kept + k, dropped + d
    log.info("%s: %d events kept, %d dropped (grounding)", ep.episode, kept, dropped)
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in raw_all).encode()
    ep.artifacts["knowledge.events.raw.jsonl"] = body  # uploaded by `publish` after the commit


def conn_show_id(conn: Connection, episode_id: int) -> int:
    e = schema.episode
    return int(conn.execute(select(e.c.show_id).where(e.c.id == episode_id)).scalar_one())
