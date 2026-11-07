"""2.9B incremental re-runs on the store: the wired pipeline (cpu stubs, replayed extraction) over
the synthetic show's S01E01-02 with en/es subtitles. An unchanged re-run is all stage-cache hits;
a new draft that edits one scene re-runs that scene's extraction and the units that read its
facts, nothing of S01E02 or of localization; `run_diff` (GET /runs/{id}/diff) says so."""

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select, update

from eval.synthetic.generate import build
from eval.synthetic.model import write_show
from nip import pipeline
from nip.api.runs import run_diff, run_status
from nip.runtime import planner
from nip.runtime.catalog import load_catalog
from nip.store import schema
from nip.store.runs import db_id
from tests.integration.test_store import EN, ES, ingest, stub_plan

pytestmark = pytest.mark.integration
EPS = ["S01E01", "S01E02"]
LINE = "I counted gulls instead of sleeping."  # first in S01E01 scene 3 (DOV), filler later


def units(pg: Engine, run_id: str) -> list[Any]:
    wu = schema.work_unit
    with pg.connect() as c:
        return list(c.execute(select(wu).where(wu.c.run_id == db_id(run_id))))


def test_edit_one_scene_reruns_only_what_reads_it(
    pg: Engine, s3: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_show(build(1), tmp_path)
    (tmp_path / "en.srt").write_text(EN, encoding="utf-8")
    (tmp_path / "es.srt").write_text(ES, encoding="utf-8")
    monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
    monkeypatch.setattr(pipeline, "AGENTS", list(pipeline.AGENTS))
    pipeline.wire()
    _, inv = stub_plan()
    plan = planner.plan(inv, load_catalog(), {sl: 2 for sl in pipeline.MODEL_SLOTS}, stub=True)
    ingest(pg, s3, [(None, tmp_path / "bible.yaml")], episode=None)
    for e in EPS:
        files = [(None, tmp_path / f"{e}.fountain"), ("en", tmp_path / "en.srt"),
                 ("es", tmp_path / "es.srt")]  # fmt: skip
        ingest(pg, s3, files, episode=e)

    def run(**kw: Any) -> dict[str, Any]:
        s = pipeline.run_store(pg, s3, show="demo", episodes=EPS, plan=plan, inventory=inv, **kw)
        assert s["status"] == "completed"
        return s

    first, same = run(), run()
    assert first["cache"]["units_cached"] == 0  # S01E02's subtitles equal S01E01's: not a hit
    assert same["cache"]["hit_rate"] == 1.0  # nothing changed: every keyed unit is a hit
    forced = run(force=True)
    assert forced["cache"]["units_cached"] == 0
    with pg.connect() as c:
        hits = c.execute(select(schema.stage_cache.c.hits)).scalars().all()
    assert hits and min(hits) >= 1

    script = (tmp_path / "S01E01.fountain").read_text(encoding="utf-8")
    draft = tmp_path / "S01E01-draft2.fountain"
    draft.write_text(script.replace(LINE, "I counted ships instead of sleeping.", 1), "utf-8")
    ingest(pg, s3, [(None, draft)], episode="S01E01")
    edited = run()

    rerun = {(u.stage, u.unit_key) for u in units(pg, edited["run_id"])
             if u.cache_key and u.status != "cached"}  # fmt: skip
    print(edited["cache"], sorted(rerun))
    assert {k for s, k in rerun if s == "knowledge.extract"} == {"S01E01/sc/3"}
    assert not [k for s, k in rerun if s.startswith("loc.") or s == "clearance.ocr"]
    # the rest read the edited scene's facts: plot rules over the whole show (they compare
    # facts across episodes, so S01E02's rule units re-run too)
    assert rerun and all(s.startswith("plot.") for s, _ in rerun - {("knowledge.extract",
                                                                      "S01E01/sc/3")})  # fmt: skip
    with pg.connect() as c:
        d = run_diff(c, edited["run_id"])
        st = run_status(c, s3, edited["run_id"])
    print(ascii(d))
    assert d["against"] == forced["run_id"]
    assert [x for x in d["changed_inputs"] if "(scenes 3 changed)" in x], d["changed_inputs"]
    assert d["units_cached"] == edited["cache"]["units_cached"] > 0
    assert d["units_rerun"] == edited["cache"]["units_rerun"]
    assert st["previous_run_id"] == d["against"] and st["status"] == "completed"
    extract = next(x for x in st["stages"] if x["stage"] == "knowledge.extract")
    assert extract["units"] - extract["cached"] == 1

    f = schema.flag  # one previous flag whose finding is gone: one resolved, one new
    with pg.begin() as c:
        fid = c.execute(select(f.c.id).where(f.c.run_id == db_id(forced["run_id"]))
                        .order_by(f.c.id).limit(1)).scalar_one()  # fmt: skip
        c.execute(update(f).where(f.c.id == fid).values(fingerprint="0" * 64))
        d2 = run_diff(c, edited["run_id"])
    assert d2["resolved_flags"] == [f"flg_{fid}"] and len(d2["new_flags"]) == 1
    assert d2["unchanged_flags"] == d["unchanged_flags"] - 1

    # a draft without the last scene deletes it with its lines, events and index chunk (2.8)
    cut = draft.read_text(encoding="utf-8").rsplit("\nINT. ", 1)[0] + "\n"
    (tmp_path / "S01E01-draft3.fountain").write_text(cut, "utf-8")
    ingest(pg, s3, [(None, tmp_path / "S01E01-draft3.fountain")], episode="S01E01")
    sc, ch, ep = schema.scene, schema.scene_chunk, schema.episode
    e1 = select(ep.c.id).where(ep.c.ref == "S01E01").scalar_subquery()
    with pg.connect() as c:
        nos = c.execute(select(sc.c.script_scene_no).where(sc.c.episode_id == e1)).scalars()
        chunks = c.execute(select(ch.c.scene_id).join(sc, sc.c.id == ch.c.scene_id)
                           .where(sc.c.episode_id == e1)).scalars().all()  # fmt: skip
    assert sorted(int(n) for n in nos) == list(range(1, 25)) and chunks
