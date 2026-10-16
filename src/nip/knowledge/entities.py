"""Entity resolution (architecture.md › Entity resolution, D-025).

A registry key from the extraction enum resolves directly. An `UNKNOWN` (or, in EXP-020's
free-text arm, any name) is fuzzy-matched against the show's names: canonical names, aliases and
secret descriptions, candidates included (rapidfuzz WRatio on lower-cased, punctuation-free text,
score >= RESOLVE_THRESHOLD, and the best score must point at one entity). A name that still does not
resolve becomes `entity(status=candidate, origin=extracted)` with the name as its alias; the
candidate is found by later events, and it appears in the review queue (`consolidate.review_queue`).
"""

from typing import Any

from rapidfuzz import fuzz, process, utils
from sqlalchemy import Connection, insert, select

from nip.store import schema

RESOLVE_THRESHOLD = 90.0  # proposed pipeline.yaml key knowledge.resolve.threshold
UNKNOWN = "UNKNOWN"
# kind of a new candidate, by its role in the event (a guess the reviewer can correct)
SUBJECT_KIND = {"setup": "prop", "payoff": "prop"}
OBJECT_KIND = {"present_at": "location", "holds": "prop", "owns": "prop", "wearing": "prop",
               "learns": "secret", "references": "secret", "relationship": "character",
               "payoff": "character", "mentions": "org"}  # fmt: skip


class Resolver:
    """Names of one show, loaded once per extraction unit (a failed unit's candidates roll back
    with its savepoint, so the index must not outlive the unit)."""

    def __init__(self, conn: Connection, show_id: int) -> None:
        self.conn, self.show_id = conn, show_id
        e, a = schema.entity, schema.entity_alias
        self.keys: dict[str, int] = {}
        self.names: list[str] = []
        self.ids: list[int] = []
        for r in conn.execute(select(e).where(e.c.show_id == show_id).order_by(e.c.id)):
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
        hits = process.extract(
            name,
            self.names,
            scorer=fuzz.WRatio,
            processor=utils.default_process,
            score_cutoff=RESOLVE_THRESHOLD,
            limit=None,
        )
        if not hits:
            return None
        best = max(s for _, s, _ in hits)
        ids = {self.ids[i] for _, s, i in hits if s == best}
        return ids.pop() if len(ids) == 1 else None

    def resolve(self, ref: str | None, name: str | None, predicate: str, role: str) -> int | None:
        """Entity id for an event argument: registry key, else matched name, else a new candidate.
        None when there is no name at all (an absent object, or UNKNOWN without a name)."""
        if ref and ref in self.keys:
            return self.keys[ref]
        surface = (name or (ref if ref != UNKNOWN else None) or "").strip()
        if not surface:
            return None
        if (eid := self.match(surface)) is not None:
            return eid
        kinds = SUBJECT_KIND if role == "subject" else OBJECT_KIND
        return self.candidate(
            surface, kinds.get(predicate, "character" if role == "subject" else "prop")
        )

    def candidate(self, name: str, kind: str) -> int:
        e = schema.entity
        values: dict[str, Any] = {"show_id": self.show_id, "kind": kind, "canonical_name": name,
                                  "origin": "extracted", "status": "candidate"}  # fmt: skip
        eid = int(self.conn.execute(insert(e).values(**values).returning(e.c.id)).scalar_one())
        self.conn.execute(
            insert(schema.entity_alias).values(entity_id=eid, alias=name, kind="name")
        )
        self._add(name, eid)
        return eid
