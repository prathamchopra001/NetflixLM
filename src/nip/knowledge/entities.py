"""Entity resolution (architecture.md › Entity resolution, D-025).

A registry key from the extraction enum resolves directly. An `UNKNOWN` (or, in EXP-020's
free-text arm, any name) is matched against the show's names: canonical names, aliases and secret
descriptions, candidates included. Both sides are lower-cased and stripped of punctuation
(rapidfuzz `default_process`, whitespace collapsed). A name scores 101 when it equals a known
name, 100 when its words are a subset of a known name's words and at least half of them ("Ada" ->
"Ada Kovac", "TOMAS" -> "Tomas Vale", but not "Tomas" -> a secret's description that names him),
else the rapidfuzz `ratio` of the whole strings (spelling slips). Whole words only: "tomato"
is not "Tom" and "Dover Street" is not "Dov"
(WRatio scored any containment at exactly 90, review I-1), and a longer name that merely contains
a known one ("Dov Street") is not it either. The best score must reach RESOLVE_THRESHOLD and point
at one entity. A name that still does not resolve becomes `entity(status=candidate,
origin=extracted)` with the name as its alias; later events find the candidate, and it appears in
the review queue (`consolidate.review_queue`).

Argument types (2.1B, EXP-006 follow-up): the quote check bounds quotation, not truth, so an event
whose resolved subject or object has the wrong entity kind for its predicate (`holds dov -> ada`,
`learns` of a location) is dropped. `ARG_KINDS` follows the predicate definitions of the prompt
(config/prompts/knowledge.extract.v1.md); a name that would become a candidate always fits, because
its kind is guessed from the same table (the first kind).
"""

from typing import Any

from rapidfuzz import fuzz, utils
from sqlalchemy import Connection, insert, select

from nip.config import pipeline_config
from nip.store import schema

RESOLVE_THRESHOLD = float(pipeline_config()["knowledge"]["resolve"]["threshold"])
UNKNOWN = "UNKNOWN"
_THINGS = ("prop", "product", "brand")
# predicate -> (subject kinds, object kinds); object None = no object expected (not checked). The
# first kind is a new candidate's kind for that role (a guess the reviewer can correct).
ARG_KINDS: dict[str, tuple[tuple[str, ...], tuple[str, ...] | None]] = {
    "present_at": (("character",), ("location",)),
    "holds": (("character",), _THINGS),
    "owns": (("character",), _THINGS),
    "wearing": (("character",), _THINGS),
    "state": (("character", "prop", "product", "location"), None),
    "learns": (("character",), ("secret",)),
    "references": (("character",), ("secret",)),
    "relationship": (("character",), ("character",)),
    "setup": (_THINGS, None),
    "payoff": (_THINGS, ("character",)),
    "decision": (("character",), None),
    "mentions": (("character",), ("org", "brand", "product", "person", "term")),
}


def score(surface: str, name: str) -> float:
    """101 for the same name; 100 when the surface's words are a subset of the name's words and at
    least half of them (not one word of a secret's description sentence); else the strings' ratio.
    The exact tier makes a repeated unresolved name find its own candidate instead of tying with the
    names that contain it ("Vale": candidate "Vale" vs "Tomas Vale", "Mira Vale")."""
    s, n = (" ".join(utils.default_process(x).split()) for x in (surface, name))
    if not s:
        return 0.0
    if s == n:  # an exact name outranks every subset match (re-review N-1)
        return 101.0
    sw, nw = set(s.split()), set(n.split())
    return 100.0 if sw <= nw and 2 * len(sw) >= len(nw) else fuzz.ratio(s, n)


class Resolver:
    """Names of one show, loaded once per extraction unit (a failed unit's candidates roll back
    with its savepoint, so the index must not outlive the unit)."""

    def __init__(self, conn: Connection, show_id: int) -> None:
        self.conn, self.show_id = conn, show_id
        e, a = schema.entity, schema.entity_alias
        self.keys: dict[str, int] = {}
        self.names: list[str] = []
        self.ids: list[int] = []
        self.kinds: dict[int, str] = {}
        for r in conn.execute(select(e).where(e.c.show_id == show_id).order_by(e.c.id)):
            self.kinds[r.id] = r.kind
            if r.status == "confirmed":
                self.keys[r.attributes.get("bible_id") or r.canonical_name] = r.id
            self._add(r.canonical_name, r.id)
            if r.kind == "secret" and r.attributes.get("description"):
                self._add(r.attributes["description"], r.id)
        for eid, alias in conn.execute(
            select(a.c.entity_id, a.c.alias)
            .join(e)
            .where(e.c.show_id == show_id, a.c.kind.in_(("name", "nickname")))
        ):
            self._add(alias, eid)

    def _add(self, name: str, eid: int) -> None:
        self.names.append(name)
        self.ids.append(eid)

    def match(self, name: str) -> int | None:
        """The one entity whose names best match `name` at >= RESOLVE_THRESHOLD, else None."""
        scores = [score(name, n) for n in self.names]
        best = max(scores, default=0.0)
        if best < RESOLVE_THRESHOLD:
            return None
        ids = {self.ids[i] for i, s in enumerate(scores) if s == best}
        return ids.pop() if len(ids) == 1 else None

    def lookup(self, ref: str | None, name: str | None) -> int | str | None:
        """An event argument's entity id (registry key, else matched name); the surface name when
        it would need a new candidate; None when there is no name at all."""
        if ref and ref in self.keys:
            return self.keys[ref]
        surface = (name or (ref if ref != UNKNOWN else None) or "").strip()
        if not surface:
            return None
        eid = self.match(surface)
        return surface if eid is None else eid

    def typed(self, predicate: str, subject: int | str | None, obj: int | str | None) -> bool:
        """Do looked-up arguments fit the predicate's kinds (ARG_KINDS)? A required object must be
        there and differ from the subject; a would-be candidate (a surface name) fits."""
        kinds, obj_kinds = ARG_KINDS[predicate]

        def fits(x: int | str, allowed: tuple[str, ...]) -> bool:
            return isinstance(x, str) or self.kinds.get(x) in allowed

        if subject is None or not fits(subject, kinds):
            return False
        return obj_kinds is None or (obj is not None and obj != subject and fits(obj, obj_kinds))

    def ensure(self, x: int | str | None, predicate: str, role: str) -> int | None:
        """`lookup`'s result as an entity id: a surface name becomes a new candidate."""
        if not isinstance(x, str):
            return x
        kinds = ARG_KINDS[predicate][0 if role == "subject" else 1]
        return self.candidate(x, kinds[0] if kinds else "prop")

    def resolve(self, ref: str | None, name: str | None, predicate: str, role: str) -> int | None:
        """Entity id for an event argument: registry key, else matched name, else a new candidate.
        None when there is no name at all (an absent object, or UNKNOWN without a name)."""
        return self.ensure(self.lookup(ref, name), predicate, role)

    def candidate(self, name: str, kind: str) -> int:
        e = schema.entity
        values: dict[str, Any] = {"show_id": self.show_id, "kind": kind, "canonical_name": name,
                                  "origin": "extracted", "status": "candidate"}  # fmt: skip
        eid = int(self.conn.execute(insert(e).values(**values).returning(e.c.id)).scalar_one())
        self.conn.execute(
            insert(schema.entity_alias).values(entity_id=eid, alias=name, kind="name")
        )
        self._add(name, eid)
        self.kinds[eid] = kind
        return eid
