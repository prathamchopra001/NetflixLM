"""Scene vector index + hybrid retrieval against Postgres (pgvector) on the synthetic show.

The show's Fountain scripts go through the real `nip ingest` writer; entities and facts come from
its `truth.json` (what 2.1 will extract), so the structured arm has facts to work with. The
planted setup/payoff pairs (truth `setups`) are the retrieval ground truth.
"""

import os
import re
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Connection, Engine, func, insert, select, text
from sqlalchemy.dialects.postgresql import Range

from eval.synthetic import build
from eval.synthetic.model import truth, write_show
from nip import pipeline
from nip.contracts import (
    Autoscaling,
    HardwareInventory,
    Mode,
    Objective,
    Plan,
    Slot,
    SlotDecision,
    StageGroup,
)
from nip.knowledge import index
from nip.knowledge.index import index_scenes
from nip.knowledge.retrieval import Filters, retrieve
from nip.runtime.clients.text_embedder import HashEmbedder
from nip.store import schema
from nip.store.ingest import ingest_files

pytestmark = pytest.mark.integration

STUB = HashEmbedder()
N_SCENES = 150


def load_synthetic(conn: Connection, s3: Any, tmp: Path) -> tuple[dict[str, Any], dict[str, int]]:
    """Ingest the 6 scripts, then add the entities and facts of `truth.json`.
    Returns (truth, scene ref -> scene id)."""
    show = build(1)
    write_show(show, tmp)
    t = truth(show)
    for ep in show.episodes:
        ingest_files(conn, s3, show=show.show, episode=ep, files=[(None, tmp / f"{ep}.fountain")])
    show_id = conn.execute(select(schema.show.c.id)).scalar_one()
    scene_ids = {
        f"{ref}/sc/{no}": sid
        for sid, ref, no in conn.execute(
            select(schema.scene.c.id, schema.episode.c.ref, schema.scene.c.script_scene_no).join(
                schema.episode, schema.episode.c.id == schema.scene.c.episode_id
            )
        )
    }
    line_ids = {
        (sid, seq): lid
        for lid, sid, seq in conn.execute(
            select(schema.script_line.c.id, schema.script_line.c.scene_id, schema.script_line.c.seq)
        )
    }
    ent = {}
    for e in t["entities"]:
        ent[e["id"]] = conn.execute(
            insert(schema.entity)
            .values(show_id=show_id, kind=e["kind"], canonical_name=e["name"], origin="bible")
            .returning(schema.entity.c.id)
        ).scalar_one()
    n = 0
    for scenes in t["episodes"].values():
        for sc in scenes:
            sid = scene_ids[sc["ref"]]
            for seq, ln in enumerate(sc["lines"], 1):
                for f in ln["facts"]:
                    subj = ent[f["subject"]]
                    obj = ent[f["object"]] if f["object"] else None
                    ev = conn.execute(
                        insert(schema.fact_event)
                        .values(
                            scene_id=sid,
                            line_id=line_ids[sid, seq],
                            predicate=f["predicate"],
                            subject_id=subj,
                            object_id=obj,
                            quote=f["quote"],
                            confidence=1.0,
                        )  # fmt: skip
                        .returning(schema.fact_event.c.id)
                    ).scalar_one()
                    n += 1  # a distinct story range per fact: the no-overlap constraint stays quiet
                    conn.execute(
                        insert(schema.fact).values(
                            show_id=show_id,
                            predicate=f["predicate"],
                            subject_id=subj,
                            object_id=obj,
                            screen=Range(n, n + 1),
                            story=Range(n, n + 1),
                            source_event_ids=[ev],
                            confidence=1.0,
                        )  # fmt: skip
                    )
    return t, scene_ids


def pair_ranks(
    conn: Connection, t: dict[str, Any], ids: dict[str, int], variant: str, weight: float, k: int
) -> list[int | None]:
    """Per planted pair: the setup scene's rank (1-based) among k hits for the payoff scene."""

    def scene(line_ref: str) -> int:  # S01E01/line/23.1 -> the scene id of S01E01/sc/23
        ep, rest = line_ref.split("/line/")
        return ids[f"{ep}/sc/{rest.split('.')[0]}"]

    out: list[int | None] = []
    for p in t["setups"]:
        got = [
            h.scene_id
            for h in retrieve(conn, scene(p["payoff"]), k, variant=variant, weight=weight)
        ]
        out.append(got.index(scene(p["setup"])) + 1 if scene(p["setup"]) in got else None)
    return out


@pytest.fixture
def synth(pg: Engine, s3: Any, tmp_path: Path) -> Any:
    with pg.begin() as conn:
        t, ids = load_synthetic(conn, s3, tmp_path)
    return pg, t, ids


def test_ingest_writes_the_speaker(synth: Any) -> None:
    pg, _, _ = synth
    with pg.connect() as conn:
        speakers = set(conn.execute(select(schema.script_line.c.speaker)).scalars())
    assert {"MAYA", "TOMAS", None} <= speakers  # dialogue has its cue, action has none


def test_index_embeds_once_and_re_embeds_only_a_changed_scene(synth: Any) -> None:
    pg, _, _ = synth
    with pg.begin() as conn:
        assert index_scenes(conn, STUB)["embedded"] == N_SCENES
        again = index_scenes(conn, STUB)
        assert (again["embedded"], again["skipped"]) == (0, N_SCENES)
        # another variant is another set of chunks
        assert index_scenes(conn, HashEmbedder("other"))["embedded"] == N_SCENES
        sid = conn.execute(select(schema.scene.c.id).limit(1)).scalar_one()
        conn.execute(
            text("UPDATE script_line SET text = 'A changed line.' WHERE scene_id = :s AND seq = 1"),
            {"s": sid},
        )
        changed = index_scenes(conn, STUB)
        assert (changed["embedded"], changed["skipped"]) == (1, N_SCENES - 1)
        n = conn.execute(text("SELECT count(*) FROM scene_chunk WHERE embedder_variant='stub'"))
        assert n.scalar_one() == N_SCENES  # replaced in place, not added


def test_hnsw_partial_index_serves_the_variants_query(synth: Any) -> None:
    pg, _, _ = synth
    variant = "qwen3-embedding-0.6b"
    with pg.begin() as conn:
        index_scenes(conn, HashEmbedder(variant))
        conn.execute(text("SET LOCAL enable_seqscan = off"))
        plan = "\n".join(
            conn.execute(
                text(
                    "EXPLAIN SELECT scene_id FROM scene_chunk"
                    f" WHERE embedder_variant = '{variant}'"
                    " ORDER BY embedding::vector(1024) <=> CAST(:q AS vector(1024)) LIMIT 5"
                ),
                {"q": str([0.1] * 1024)},
            ).scalars()
        )
    assert "ix_scene_chunk_hnsw_qwen3_embedding_0_6b" in plan


def test_retrieval_is_deterministic_excludes_itself_and_respects_filters(synth: Any) -> None:
    pg, t, ids = synth
    with pg.begin() as conn:
        index_scenes(conn, STUB)
        sid = ids["S01E03/sc/24"]  # the lantern setup scene
        hits = retrieve(conn, sid, 10, variant="stub")
        assert hits == retrieve(conn, sid, 10, variant="stub")
        assert sid not in [h.scene_id for h in hits] and len(hits) == 10
        assert all(re.fullmatch(r"S01E0\d/sc/\d+", h.ref) for h in hits)
        assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)

        props = retrieve(
            conn, sid, 10, variant="stub", filters=Filters(kinds=["prop"], shared_only=True)
        )
        assert props and all(h.shared and h.overlap > 0 for h in props)
        only_ep4 = [
            h.scene_id
            for h in retrieve(conn, sid, 10, variant="stub", filters=Filters(episode_ids=[4]))
        ]
        ep4 = set(
            conn.execute(
                text(
                    "SELECT s.id FROM scene s JOIN episode e ON e.id = s.episode_id"
                    " WHERE e.ref = 'S01E04'"
                )
            ).scalars()
        )
        assert only_ep4 and set(only_ep4) <= ep4

        with pytest.raises(LookupError):
            retrieve(conn, sid, 5, variant="not-indexed")


def test_shared_props_lift_the_setup_scene_over_vector_only(synth: Any) -> None:
    pg, t, ids = synth
    with pg.begin() as conn:
        index_scenes(conn, STUB)
        vec = pair_ranks(conn, t, ids, "stub", 0.0, N_SCENES)
        hyb = pair_ranks(conn, t, ids, "stub", 0.5, N_SCENES)
    print("stub vector-only ranks", vec, "hybrid ranks", hyb)
    assert all(h is not None and v is not None and h <= v for h, v in zip(hyb, vec, strict=True))
    assert hyb != vec  # the structured arm moved something


@pytest.mark.skipif(not os.environ.get("NIP_INDEX_REAL"), reason="NIP_INDEX_REAL not set")
def test_real_embedder_ranks(synth: Any) -> None:
    from nip.runtime.clients.text_embedder import make_embedder

    pg, t, ids = synth
    emb = make_embedder("qwen3-embedding-0.6b", device=os.environ["NIP_INDEX_REAL"])
    import time

    with pg.begin() as conn:
        t0 = time.perf_counter()
        index_scenes(conn, emb)
        dt = time.perf_counter() - t0
        for w in (0.0, 0.25, 0.5, 1.0):
            print("real w", w, pair_ranks(conn, t, ids, emb.variant, w, N_SCENES))
    print(f"real index {N_SCENES} scenes {dt:.1f}s on {os.environ['NIP_INDEX_REAL']}")


@pytest.mark.parametrize("asked", [True, False])
def test_stage_indexes_the_episode_with_the_plans_embedder(
    synth: Any, s3: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, asked: bool
) -> None:
    pg, _, _ = synth
    inv = HardwareInventory(
        fingerprint="f", nodes=[], autoscaling=Autoscaling(enabled=False, max_gpu_nodes=0)
    )
    decisions = {Slot.TEXT_EMBEDDER: SlotDecision(variant="stub")} if asked else {}
    plan = Plan(
        inventory_fingerprint="f", catalog_sha256="c", objective=Objective.QUALITY,
        mode=Mode.RESIDENT, groups=[StageGroup(name="resident", slots=[])], decisions=decisions,
    )  # fmt: skip
    monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
    pipeline.add_stage("knowledge.index", index.stage)
    pipeline.run_store(pg, s3, show="synthetic-show", episodes=["S01E02"], plan=plan, inventory=inv)
    with pg.connect() as conn:
        chunks = conn.execute(select(func.count()).select_from(schema.scene_chunk)).scalar_one()
        units = conn.execute(
            select(schema.work_unit.c.unit_key, schema.work_unit.c.status).where(
                schema.work_unit.c.stage == "knowledge.index"
            )
        ).all()
    if asked:  # one episode = 25 scenes, one unit
        assert chunks == 25 and [tuple(u) for u in units] == [("S01E02", "done")]
    else:
        assert chunks == 0 and units == []
