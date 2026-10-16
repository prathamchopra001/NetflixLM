"""Consolidation: scene-local fact events -> timed facts (data-model.md › Knowledge layer).

Deterministic and cheap, so it re-runs over the whole show whenever events change (the
`knowledge.consolidate` stage runs after every episode's extraction). Events are taken in story
order (story_seq, then screen position); intervals are half-open, in story_seq units (`story`) and
screen_key units (`screen`, `(episode_seq << 32) | frame`):

- present_at, references, mentions, decision, setup, payoff: the scene's own range.
- learns; state dead / destroyed: open-ended from the event.
- holds, owns: from a holder's first event until the same object is held by someone else, is
  given or lost (value give/lose/lost/drop/sell), or is destroyed or lost (a `state` of the
  object; a lose/lost/drop value also yields the object's `state: lost` fact, from the same
  event); the holder's later events continue it (a use stays a `holds` event with value
  `{"event": "use"}` inside the holder's fact, as 2.3's plot.prop_provenance reads it).
- wearing: until the same garment is removed (value remove/drop).
- relationship: until the same pair gets another kind.
- state, other values: until the subject's next state with another value (`healed` ends
  `injured`).

A closed interval ends where the superseding event starts (at least one unit long; on screen,
at the start of the superseding scene, or the end of the fact's own last scene when that scene is
not earlier on screen). Finally, facts with the same subject, predicate and object (and, when there
is no object, the same value) whose story ranges overlap merge into one: union of ranges and source
events, the first event's value, minimum confidence. That is the `fact_consolidated_no_overlap`
invariant. Confidence = min of the source events, times NIP_INFERRED_STORY_CONFIDENCE_FACTOR when
a source scene's story position is inferred.

Story positions come from `scene.story_seq` when every scene of the show has one (2.2), else from
script order (episode_seq, then scene order) with nothing inferred.
"""

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Connection, insert, select, update
from sqlalchemy.dialects.postgresql import Range

from nip.contracts.fact import Fact, Predicate
from nip.store import schema

STAGE = "knowledge.consolidate"
FACT_REVIEW_THRESHOLD = float(os.environ.get("NIP_FACT_REVIEW_THRESHOLD", "0.80"))
INFERRED_FACTOR = float(os.environ.get("NIP_INFERRED_STORY_CONFIDENCE_FACTOR", "0.85"))
POINT = {"present_at", "references", "mentions", "decision", "setup", "payoff"}
TERMINAL = {"dead", "destroyed"}
GONE = {"destroyed", "lost"}  # a state of an object that ends its holds/owns/wearing
END = {"give", "lose", "lost", "drop", "sell", "remove"}  # holds/owns/wearing values
LOSS = {"lose", "lost", "drop"}  # holds/owns values that also make the object `state: lost`


@dataclass(frozen=True)
class Event:
    id: int
    scene_id: int
    predicate: str
    subject_id: int
    object_id: int | None
    value: dict[str, Any] | None
    confidence: float


@dataclass(frozen=True)
class Pos:
    story: int  # story_seq
    screen: tuple[int, int]  # screen_key range of the scene
    inferred: bool = False


@dataclass
class _Draft:
    first: Event
    head: str | None
    story: tuple[int, int | None]
    screen: tuple[int, int | None]
    last_screen: int  # end of the latest source scene on screen
    events: list[Event] = field(default_factory=list)
    inferred: bool = False

    def add(self, e: Event, p: Pos) -> None:
        self.events.append(e)
        self.inferred |= p.inferred
        self.last_screen = max(self.last_screen, p.screen[1])


def head(e: Event) -> str | None:
    """The value's first entry, lower-cased: the state, holds event, relationship kind..."""
    v = next(iter(e.value.values()), None) if e.value else None
    return str(v).lower() if v is not None else None


def _closes(e: Event, h: str | None, d: _Draft) -> bool:
    """Does event `e` (value head `h`) end the open interval `d`?"""
    f = d.first
    if f.predicate == e.predicate and f.predicate in ("state", "relationship"):
        return f.subject_id == e.subject_id and f.object_id == e.object_id and h != d.head
    if f.predicate == e.predicate:  # holds, owns, wearing
        other_holder = f.subject_id != e.subject_id and f.predicate != "wearing"
        return f.object_id == e.object_id and (h in END or other_holder)
    return e.predicate == "state" and h in GONE and f.object_id == e.subject_id


def _upper(a: int | None, b: int | None) -> int | None:
    return None if a is None or b is None else max(a, b)


def _merge(drafts: list[_Draft]) -> list[_Draft]:
    def key(d: _Draft) -> tuple[Any, ...]:
        f = d.first
        v = json.dumps(f.value, sort_keys=True) if f.object_id is None else ""
        return f.subject_id, f.predicate, f.object_id or 0, v  # ids start at 1

    out: list[_Draft] = []
    for d in sorted(drafts, key=lambda d: (key(d), d.story[0], d.first.id)):
        prev = out[-1] if out else None
        if prev and key(prev) == key(d) and (prev.story[1] is None or d.story[0] < prev.story[1]):
            prev.story = (prev.story[0], _upper(prev.story[1], d.story[1]))
            prev.screen = (min(prev.screen[0], d.screen[0]), _upper(prev.screen[1], d.screen[1]))
            prev.events += d.events
            prev.inferred |= d.inferred
        else:
            out.append(d)
    return out


def consolidate(events: Iterable[Event], pos: dict[int, Pos], show_id: int) -> list[Fact]:
    """Timed facts from the show's events (see the module docstring for the rules)."""
    drafts: list[_Draft] = []
    open_: dict[tuple[Any, ...], _Draft] = {}

    def start(e: Event, p: Pos, h: str | None, open_ended: bool) -> _Draft:
        story = (p.story, None if open_ended else p.story + 1)
        screen = (p.screen[0], None if open_ended else p.screen[1])
        d = _Draft(e, h, story, screen, p.screen[1])
        d.add(e, p)
        drafts.append(d)
        return d

    events = list(events)
    events += [  # a lost or dropped prop: also `state: lost` of the prop (2.3 prop_provenance)
        Event(e.id, e.scene_id, "state", e.object_id, None, {"state": "lost"}, e.confidence)
        for e in events
        if e.predicate in ("holds", "owns") and head(e) in LOSS and e.object_id is not None
    ]
    ordered = sorted(events, key=lambda e: (pos[e.scene_id].story, pos[e.scene_id].screen[0], e.id))
    for e in ordered:
        p, h = pos[e.scene_id], head(e)
        for k, d in list(open_.items()):
            if _closes(e, h, d):
                d.story = (d.story[0], max(p.story, d.story[0] + 1))
                d.screen = (
                    d.screen[0],
                    p.screen[0] if p.screen[0] > d.screen[0] else d.last_screen,
                )
                del open_[k]
        if e.predicate in POINT:
            start(e, p, h, open_ended=False)
        elif e.predicate == "learns" or (e.predicate == "state" and h in TERMINAL):
            start(e, p, h, open_ended=True)
        elif e.predicate in ("state", "relationship") or h not in END:  # holds, owns, wearing
            k = (e.predicate, e.subject_id, e.object_id)
            k += (h,) if e.predicate in ("state", "relationship") else ()
            if k in open_:
                open_[k].add(e, p)
            else:
                open_[k] = start(e, p, h, open_ended=True)
    facts = []
    for d in _merge(drafts):
        conf = min(e.confidence for e in d.events) * (INFERRED_FACTOR if d.inferred else 1.0)
        f = d.first
        facts.append(
            Fact(
                show_id=show_id,
                predicate=Predicate(f.predicate),
                subject_id=f.subject_id,
                object_id=f.object_id,
                value=f.value,
                screen=d.screen,
                story=d.story,
                source_event_ids=sorted(e.id for e in d.events),
                confidence=round(conf, 4),
            )
        )
    return facts


# ---- store -------------------------------------------------------------------------------------


def positions(conn: Connection, show_id: int) -> dict[int, Pos]:
    """scene id -> story/screen position, for every scene of the show (see module docstring)."""
    sc, ep = schema.scene, schema.episode
    rows = conn.execute(
        select(sc.c.id, sc.c.frames, sc.c.story_seq, sc.c.story_inferred, ep.c.episode_seq)
        .join(ep, ep.c.id == sc.c.episode_id)
        .where(ep.c.show_id == show_id)
        .order_by(ep.c.episode_seq, sc.c.id)
    ).all()
    explicit = bool(rows) and all(r.story_seq is not None for r in rows)
    out = {}
    for rank, r in enumerate(rows, 1):
        base = r.episode_seq << 32
        lo, hi = (r.frames.lower, r.frames.upper) if r.frames is not None else (0, 1)
        story = r.story_seq if explicit else rank
        out[r.id] = Pos(story, (base | lo, base | hi), bool(r.story_inferred) and explicit)
    return out


def load_events(conn: Connection, show_id: int) -> list[Event]:
    fe, sc, ep = schema.fact_event, schema.scene, schema.episode
    rows = conn.execute(
        select(
            fe.c.id,
            fe.c.scene_id,
            fe.c.predicate,
            fe.c.subject_id,
            fe.c.object_id,
            fe.c.value,
            fe.c.confidence,
        )  # fmt: skip
        .join(sc, sc.c.id == fe.c.scene_id)
        .join(ep, ep.c.id == sc.c.episode_id)
        .where(ep.c.show_id == show_id)
        .order_by(fe.c.id)
    ).all()
    return [Event(*r) for r in rows]


def write_facts(conn: Connection, show_id: int, facts: list[Fact]) -> None:
    """The show's active facts become `superseded`; `facts` are inserted active."""
    fa = schema.fact
    conn.execute(
        update(fa)
        .where(fa.c.show_id == show_id, fa.c.status == "active")
        .values(status="superseded")
    )
    if facts:
        conn.execute(
            insert(fa),
            [
                f.model_dump(
                    include={
                        "show_id",
                        "predicate",
                        "subject_id",
                        "object_id",
                        "value",
                        "source_event_ids",
                        "confidence",
                    },
                    mode="json",
                )  # fmt: skip
                | {"screen": Range(*f.screen), "story": Range(*f.story)}
                for f in facts
            ],
        )


def consolidate_show(conn: Connection, show_id: int) -> int:
    """Re-consolidate every event of the show; returns the number of active facts."""
    facts = consolidate(load_events(conn, show_id), positions(conn, show_id), show_id)
    write_facts(conn, show_id, facts)
    return len(facts)


def review_queue(
    conn: Connection, show_id: int, threshold: float = FACT_REVIEW_THRESHOLD
) -> dict[str, list[Any]]:
    """The fact correction queue (architecture.md › Fact correction loop): active facts below
    `threshold` (NIP_FACT_REVIEW_THRESHOLD) and candidate entities, lowest confidence first."""
    fa, e = schema.fact, schema.entity
    facts = conn.execute(
        select(fa)
        .where(fa.c.show_id == show_id, fa.c.status == "active", fa.c.confidence < threshold)
        .order_by(fa.c.confidence, fa.c.id)
    ).all()
    cands = conn.execute(
        select(e).where(e.c.show_id == show_id, e.c.status == "candidate").order_by(e.c.id)
    ).all()
    return {"facts": list(facts), "candidates": list(cands)}


def stage_consolidate(ep: Any) -> None:
    """Pipeline stage `knowledge.consolidate` (`fn(ep: EpisodeRun)`), one unit per show pass."""
    e = schema.episode
    show_id = ep.conn.execute(select(e.c.show_id).where(e.c.id == ep.episode_id)).scalar_one()
    with ep.unit(STAGE, f"{ep.show}/{ep.episode}"):
        consolidate_show(ep.conn, show_id)
