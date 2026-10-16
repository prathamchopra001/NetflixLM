"""2.1 on the store: the synthetic show extracted end to end (cpu profile: recorded responses),
grounding drops in the stored path, candidates, consolidation into `fact`, the review queue."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import Engine, func, select

from eval.synthetic import build, write_show
from nip import pipeline
from nip.knowledge import extract
from nip.knowledge.consolidate import review_queue, stage_consolidate
from nip.knowledge.extract import stage_extract
from nip.store import schema
from nip.store.ingest import ingest_files
from nip.store.load import load_timeline
from tests.integration.conftest import FakeS3
from tests.integration.test_store import stub_plan

pytestmark = pytest.mark.integration
SHOW = "synthetic-show"


def ingest_show(pg: Engine, s3: FakeS3, d: Path, episodes: tuple[str, ...] = ("S01E01",)) -> None:
    write_show(build(1), d)
    with pg.begin() as conn:
        ingest_files(conn, s3, show=SHOW, episode=None, files=[(None, d / "bible.yaml")])
        for ep in episodes:
            ingest_files(conn, s3, show=SHOW, episode=ep, files=[(None, d / f"{ep}.fountain")])


def run(
    pg: Engine, s3: FakeS3, monkeypatch: pytest.MonkeyPatch, episode: str = "S01E01"
) -> dict[str, Any]:
    if extract.STAGE not in dict(pipeline.STAGES):  # once per test
        monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
        pipeline.add_stage(extract.STAGE, stage_extract)
        pipeline.add_stage("knowledge.consolidate", stage_consolidate)
    plan, inv = stub_plan()
    return pipeline.run_store(pg, s3, show=SHOW, episodes=[episode], plan=plan, inventory=inv)


def count(pg: Engine, t: Any, *where: Any) -> int:
    with pg.connect() as c:
        return int(c.execute(select(func.count()).select_from(t).where(*where)).scalar_one())


def test_synthetic_show_extracts_on_the_cpu_profile(
    pg: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    s3 = FakeS3()
    ingest_show(pg, s3, tmp_path)
    s = run(pg, s3, monkeypatch)
    assert s["status"] == "completed" and s["episodes"]["S01E01"]["units"] == {"done": 26}
    fe, fa = schema.fact_event, schema.fact
    n_events, n_facts = count(pg, fe), count(pg, fa, fa.c.status == "active")
    # replayed qwen3.5-4b-awq responses (EXP-020 enum pass): its 75 S01E01 events, all grounded
    assert n_events == 75 and 0 < n_facts <= n_events
    raw = s3.objects["nip-artifacts", "runs/run_1/S01E01/knowledge.events.raw.jsonl"].decode()
    assert len(raw.splitlines()) >= n_events
    first = active_ids(pg)
    # a second run re-extracts (new event ids) but changes no fact: same ids, no new rows (I-2)
    s2 = run(pg, s3, monkeypatch)
    assert s2["status"] == "completed" and count(pg, fe) == n_events
    assert active_ids(pg) == first and count(pg, fa) == len(first)
    # the next episode's consolidation keeps S01E01's unchanged facts and their evidence refs
    with pg.begin() as conn:
        f = tmp_path / "S01E02.fountain"
        ingest_files(conn, s3, show=SHOW, episode="S01E02", files=[(None, f)])
    assert run(pg, s3, monkeypatch, "S01E02")["status"] == "completed"
    kept = first & active_ids(pg)
    assert len(kept) >= 0.8 * len(first)
    with pg.connect() as conn:
        tl = load_timeline(conn, SHOW, "S01E01")
        # kept and superseded facts both resolve, so S01E01's fact evidence stays checkable (W-int)
        assert all(tl.resolve(f"fact/{i}") is not None for i in first)
        assert first - kept, "S01E02 closes at least one S01E01 fact"
        for old in first - kept:  # closed by an S01E02 event: superseded, with a successor
            succ = conn.execute(select(fa.c.id).where(fa.c.supersedes == old)).first()
            status = conn.execute(select(fa.c.status).where(fa.c.id == old)).scalar_one()
            assert status == "superseded" and succ is not None


def active_ids(pg: Engine) -> set[int]:
    fa = schema.fact
    with pg.connect() as c:
        return set(c.execute(select(fa.c.id).where(fa.c.status == "active")).scalars())


class FakeLLM:
    variant = "fake"

    def complete(self, prompt: str, schema_: type[BaseModel], **kw: Any) -> BaseModel:
        if "[1] (action)" not in prompt or "Scene:\nINT. " not in prompt:
            return schema_.model_validate({"events": []})
        line1 = prompt.split("[1] (action) ", 1)[1].split("\n", 1)[0]
        events = [
            {
                "line": 1,
                "quote": line1[:25],
                "predicate": "present_at",
                "subject": "UNKNOWN",
                "subject_name": "Captain Nobody",
                "object": "UNKNOWN",
                "object_name": "Nowhere Pier",
                "confidence": 0.5,
            },
            {
                "line": 1,
                "quote": "Ada Kovac is the informant",
                "predicate": "learns",
                "subject": "maya",
                "object": "secret_1",
                "confidence": 0.99,
            },  # fabricated quote
        ]
        return schema_.model_validate({"events": events}, context=kw.get("context"))


def test_fabricated_quotes_are_dropped_and_unknown_names_become_candidates(
    pg: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    s3 = FakeS3()
    ingest_show(pg, s3, tmp_path)
    monkeypatch.setattr(extract, "text_llm", lambda plan: FakeLLM())
    s = run(pg, s3, monkeypatch)
    assert s["status"] == "completed"
    fe, e = schema.fact_event, schema.entity
    with pg.connect() as conn:
        quotes = conn.execute(select(fe.c.quote)).scalars().all()
        assert quotes and "Ada Kovac is the informant" not in quotes  # every fabricated one dropped
        cands = conn.execute(
            select(e.c.canonical_name, e.c.kind, e.c.origin).where(e.c.status == "candidate")
        ).all()
        # one candidate per name, reused by every later scene
        assert sorted(map(tuple, cands)) == [
            ("Captain Nobody", "character", "extracted"),
            ("Nowhere Pier", "location", "extracted"),
        ]
        ln = schema.script_line
        spoken = conn.execute(select(ln.c.speaker_entity_id).where(ln.c.kind == "dialogue")).all()
        assert spoken and all(r.speaker_entity_id is not None for r in spoken)  # MAYA -> maya
        show_id = conn.execute(select(schema.show.c.id)).scalar_one()
        q = review_queue(conn, show_id)
    assert [c.canonical_name for c in q["candidates"]] == ["Captain Nobody", "Nowhere Pier"]
    assert q["facts"] and all(f.confidence < 0.8 for f in q["facts"])  # the 0.5 present_at facts
    raw = s3.objects["nip-artifacts", "runs/run_1/S01E01/knowledge.events.raw.jsonl"].decode()
    rows = [json.loads(r) for r in raw.splitlines()]
    dropped = [r for r in rows if not r["grounded"]]  # raw keeps the dropped, with the verdict
    assert dropped and all(r["quote"] == "Ada Kovac is the informant" for r in dropped)
    assert len(rows) - len(dropped) == len(quotes)
