"""Hybrid scene retrieval: vector similarity plus overlap of the entities the scenes' active facts
share. No LLM. architecture.md › Scene vector index.

    score = cosine similarity + weight * overlap
    overlap = IDF-weighted share of the query scene's entities that the candidate also has

An entity is "in" a scene when an active fact whose source events are in that scene has it as
subject or object. IDF (log of scenes over scenes with the entity) makes a prop or a secret count
for more than a main character who is in every scene. The vector arm uses the HNSW index; the
candidate pool is its top max(10k, 50) plus every scene sharing an entity, then re-ranked.
"""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Connection, Text, cast, func, select, text

from nip.contracts import refs
from nip.knowledge.index import KIND
from nip.runtime.clients.text_embedder import EMBED_DIM
from nip.store import schema

WEIGHT = 1.0  # picked from a weight sweep on the 3 synthetic pairs (notes/2.8.md): little data
_VARIANT = re.compile(r"[\w.\-]+")


@dataclass(frozen=True)
class Filters:
    kinds: Sequence[str] | None = None  # entity kinds that count for overlap (prop, secret, ...)
    shared_only: bool = False  # drop scenes that share no counted entity
    episode_ids: Sequence[int] | None = None  # restrict candidates to these episodes


@dataclass(frozen=True)
class Hit:
    scene_id: int
    ref: str  # S01E03/sc/24
    score: float
    sim: float
    overlap: float
    shared: tuple[int, ...]  # entity ids shared with the query scene


_ENTITIES = text("""
    SELECT DISTINCT fe.scene_id, v.ent, ent.kind
    FROM fact f
    JOIN fact_event fe ON fe.id = ANY(f.source_event_ids)
    CROSS JOIN LATERAL (VALUES (f.subject_id), (f.object_id)) AS v(ent)
    JOIN entity ent ON ent.id = v.ent
    WHERE f.show_id = :show AND f.status = 'active'
""")


def _entities(conn: Connection, show_id: int, kinds: Sequence[str] | None) -> dict[int, set[int]]:
    out: dict[int, set[int]] = {}
    for scene_id, ent, kind in conn.execute(_ENTITIES, {"show": show_id}):
        if kinds is None or kind in kinds:
            out.setdefault(scene_id, set()).add(ent)
    return out


def retrieve(
    conn: Connection,
    scene_id: int,
    k: int = 5,
    *,
    variant: str,
    filters: Filters | None = None,
    weight: float = WEIGHT,
) -> list[Hit]:
    """The k scenes of the same show most related to `scene_id`, best first. The scene must be
    indexed for `variant` (`index.index_scenes`)."""
    f = filters or Filters()
    if not _VARIANT.fullmatch(variant):
        raise ValueError(f"bad embedder variant {variant!r}")
    sc, ep, c = schema.scene, schema.episode, schema.scene_chunk
    q = conn.execute(
        select(cast(c.c.embedding, Text), ep.c.show_id)
        .select_from(c.join(sc, sc.c.id == c.c.scene_id).join(ep, ep.c.id == sc.c.episode_id))
        .where(c.c.scene_id == scene_id, c.c.kind == KIND, c.c.embedder_variant == variant)
    ).one_or_none()
    if q is None:
        raise LookupError(f"scene {scene_id} has no {KIND} chunk for {variant}")
    qvec, show_id = q
    n_pool = max(10 * k, 50)
    # The variant is inlined (checked above): the partial HNSW index is used only when the planner
    # can see its predicate. Iterative scan keeps the post-filter (show) from starving the result.
    conn.execute(text("SELECT set_config('hnsw.iterative_scan', 'strict_order', true)"))
    conn.execute(text(f"SELECT set_config('hnsw.ef_search', '{min(max(n_pool, 40), 1000)}', true)"))
    vec = f"CAST(:q AS vector({EMBED_DIM}))"
    sim_sql = f"""
        SELECT c.scene_id, e.ref, s.script_scene_no,
               1 - (c.embedding::vector({EMBED_DIM}) <=> {vec}) AS sim
        FROM scene_chunk c JOIN scene s ON s.id = c.scene_id JOIN episode e ON e.id = s.episode_id
        WHERE c.kind = '{KIND}' AND c.embedder_variant = '{variant}' AND e.show_id = :show
          AND c.scene_id <> :sid AND (CAST(:eps AS bigint[]) IS NULL OR s.episode_id = ANY(:eps))
    """
    params = {
        "q": qvec,
        "show": show_id,
        "sid": scene_id,
        "eps": list(f.episode_ids) if f.episode_ids is not None else None,
    }
    order = f" ORDER BY c.embedding::vector({EMBED_DIM}) <=> {vec} LIMIT {n_pool}"
    rows = {r.scene_id: r for r in conn.execute(text(sim_sql + order), params)}
    ents = _entities(conn, show_id, f.kinds)
    mine = ents.get(scene_id, set())
    extra = [s for s, e in ents.items() if s != scene_id and s not in rows and e & mine]
    if extra:
        more = conn.execute(
            text(sim_sql + " AND c.scene_id = ANY(:extra)"), params | {"extra": extra}
        )
        rows |= {r.scene_id: r for r in more}
    n_scenes = conn.execute(
        select(func.count())
        .select_from(sc.join(ep, ep.c.id == sc.c.episode_id))
        .where(ep.c.show_id == show_id)
    ).scalar_one()
    df: dict[int, int] = {}
    for es in ents.values():
        for e in es:
            df[e] = df.get(e, 0) + 1
    idf = {e: math.log(n_scenes / n) for e, n in df.items()}
    total = sum(idf[e] for e in mine)
    hits = []
    for r in rows.values():
        shared = mine & ents.get(r.scene_id, set())
        if f.shared_only and not shared:
            continue
        overlap = sum(idf[e] for e in shared) / total if total > 0 else 0.0
        score = r.sim + weight * overlap
        ref = refs.scene(r.ref, r.script_scene_no)
        hits.append(Hit(r.scene_id, ref, score, r.sim, overlap, tuple(sorted(shared))))
    return sorted(hits, key=lambda h: (-h.score, h.scene_id))[:k]
