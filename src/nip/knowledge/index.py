"""Scene vector index: one `scene_chunk(kind='scene_text')` per scene and embedder variant.

architecture.md › Scene vector index, D-017: the text of the scene only (heading, action, dialogue
with its speaker), so the index is buildable before any extraction. A scene is embedded once per
(text, variant): a chunk whose stored text equals the scene's current text is skipped, a changed
scene is re-embedded in place (UNIQUE scene_id, kind, variant).

Wiring (W-int): `pipeline.add_stage("knowledge.index", index.stage)`, with a `text_embedder`
workload in the Plan.
"""

import logging
from collections import Counter
from collections.abc import Sequence
from functools import cache
from typing import TYPE_CHECKING

from sqlalchemy import Connection, select
from sqlalchemy.dialects.postgresql import insert

from nip.contracts import Slot
from nip.runtime.clients.text_embedder import TextEmbedder, make_embedder
from nip.store import schema

if TYPE_CHECKING:
    from nip.pipeline import EpisodeRun

log = logging.getLogger(__name__)

KIND = "scene_text"
STAGE = "knowledge.index"
Line = tuple[str, str | None, str]  # (kind, speaker, text)


def scene_text(heading: str, lines: Sequence[Line]) -> str:
    """Heading, then each line: dialogue as `SPEAKER: text`, a parenthetical in parentheses, a
    transition dropped."""
    out = [heading]
    for kind, speaker, text in lines:
        if kind == "transition":
            continue
        if kind == "parenthetical":
            text = f"({text})"
        out.append(f"{speaker}: {text}" if speaker and kind == "dialogue" else text)
    return "\n".join(out)


def scene_texts(conn: Connection, episode_ids: Sequence[int] | None = None) -> dict[int, str]:
    """scene id -> its text, for the given episodes (all when None)."""
    sc, ln = schema.scene, schema.script_line
    q = select(sc.c.id, sc.c.heading, ln.c.kind, ln.c.speaker, ln.c.text).select_from(
        sc.outerjoin(ln, ln.c.scene_id == sc.c.id)
    )
    if episode_ids is not None:
        q = q.where(sc.c.episode_id.in_(episode_ids))
    heads: dict[int, str] = {}
    lines: dict[int, list[Line]] = {}
    for sid, head, kind, speaker, text in conn.execute(q.order_by(sc.c.id, ln.c.seq)):
        heads[sid] = head
        if kind is not None:
            lines.setdefault(sid, []).append((kind, speaker, text))
    return {sid: scene_text(h, lines.get(sid, [])) for sid, h in heads.items()}


def index_scenes(
    conn: Connection,
    embedder: TextEmbedder,
    episode_ids: Sequence[int] | None = None,
    batch_size: int = 16,
) -> Counter[str]:
    """Embed the scenes of `episode_ids` that have no up-to-date chunk for this embedder's variant.
    Returns {"embedded": n, "skipped": n}."""
    texts = scene_texts(conn, episode_ids)
    c = schema.scene_chunk
    have = dict(
        conn.execute(
            select(c.c.scene_id, c.c.text).where(
                c.c.kind == KIND,
                c.c.embedder_variant == embedder.variant,
                c.c.scene_id.in_(list(texts)),
            )
        ).all()
    )
    todo = [(sid, t) for sid, t in texts.items() if have.get(sid) != t]
    step = batch_size * 8  # a few model batches per INSERT
    for i in range(0, len(todo), step):
        part = todo[i : i + step]
        vectors = embedder.embed([t for _, t in part], batch_size)
        ins = insert(c)
        conn.execute(
            ins.on_conflict_do_update(
                index_elements=[c.c.scene_id, c.c.kind, c.c.embedder_variant],
                set_={"text": ins.excluded.text, "embedding": ins.excluded.embedding},
            ),
            [
                {
                    "scene_id": sid,
                    "kind": KIND,
                    "text": t,
                    "embedding": v,
                    "embedder_variant": embedder.variant,
                }
                for (sid, t), v in zip(part, vectors, strict=True)
            ],
        )
    return Counter(embedded=len(todo), skipped=len(texts) - len(todo))


@cache
def _embedder(variant: str) -> TextEmbedder:
    from nip.runtime.catalog import load_catalog  # the catalog decides stub vs model

    return make_embedder(variant, load_catalog())


def stage(ep: "EpisodeRun") -> None:
    """Pipeline stage: embed this episode's scenes with the Plan's text embedder. No decision for
    the slot (no workload asked for one) -> nothing to do."""
    decision = ep.plan.decisions.get(Slot.TEXT_EMBEDDER)
    if decision is None:
        return
    with ep.unit(STAGE, ep.episode, model_variant=decision.variant):
        stats = index_scenes(ep.conn, _embedder(decision.variant), [ep.episode_id])
        log.info("%s %s: %s", STAGE, ep.episode, dict(stats))
