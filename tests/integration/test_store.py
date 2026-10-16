"""Store spine (2.0): `nip ingest` rows, `load_timeline` == `build_timeline`, run/flag persistence.

Postgres via the `pg` fixture (NIP_TEST_DATABASE_URL), S3 via the in-memory `s3` fake.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, func, insert, select, text, update
from typer.testing import CliRunner

from nip import pipeline
from nip.cli import app
from nip.contracts import (
    Autoscaling,
    Flag,
    HardwareInventory,
    Mode,
    Objective,
    Plan,
    StageGroup,
)
from nip.contracts.flag import EvidenceKind
from nip.ingest import parse
from nip.ingest.media import probe
from nip.store import objects, schema
from nip.store.ingest import InputRejected, ingest_files
from nip.store.load import load_timeline
from nip.timeline.estimate import build_timeline

pytestmark = pytest.mark.integration

SCRIPT = (
    "INT. ROOM - DAY #1#\n\nMaya enters.\n\nMAYA\nHello there.\n\nEXT. DOCK - NIGHT #2#\n\nRain.\n"
)
EN = "1\n00:00:01,000 --> 00:00:03,000\nHello.\n\n2\n00:00:04,000 --> 00:00:06,000\nBye.\n"
ES = (  # cue 2 has 3 lines; cue 3 starts 1 frame after cue 2 ends: 2 readability flags
    "1\n00:00:01,000 --> 00:00:03,000\nHola.\n\n"
    "2\n00:00:04,000 --> 00:00:06,000\nuno\ndos\ntres\n\n"
    "3\n00:00:06,042 --> 00:00:08,000\nAdiós.\n"
)
BIBLE = """show: demo
characters:
  - {id: maya, name: Maya Reyes, aliases: [May], gender: female}
secrets:
  - {id: maya_is_informant, description: Maya is the informant}
fictional:
  brands: [Kappa Cola]
  places: [Harbor Warehouse]
"""
GLOSSARY = "term,lang,approved_rendering,notes\nthe Hollow,es,el Hueco,\n"
CLEARANCE = "item,kind,status,scope,notes\nAcme Hardware,logo,pending,S01E01,legal\n"
SHOTS = [[0, 72], [72, 144]]
KEYFRAMES = [
    {"shot": 0, "n": 0, "frame": 36, "file": "0_0.jpg"},
    {"shot": 1, "n": 0, "frame": 108, "file": "1_0.jpg"},
]


def write(d: Path, files: dict[str, str]) -> dict[str, Path]:
    for name, body in files.items():
        (d / name).write_text(body, encoding="utf-8")
    return {name: d / name for name in files}


def clip(d: Path, fps: int = 24) -> Path:
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not on PATH")
    out = d / f"clip{fps}.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=160x90:rate={fps}:duration=6",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(out),
        ],
        check=True,
    )
    return out


def picture_json(d: Path, video: Path) -> Path:
    m = probe(video)
    (d / "keyframes").mkdir(exist_ok=True)
    (d / "keyframes" / "0_0.jpg").write_bytes(b"jpg")  # 1_0.jpg missing: no object_key
    p = d / "picture.json"
    pic = {
        "fps": [m.fps.numerator, m.fps.denominator],
        "duration_frames": m.duration_frames,
        "start_tc_frames": 0,
        "drop_frame": False,
        "shots": SHOTS,
        "keyframes": KEYFRAMES,
    }
    p.write_text(json.dumps(pic), encoding="utf-8")
    return p


def counts(pg: Engine) -> dict[str, int]:
    with pg.connect() as c:
        return {
            t.name: c.execute(select(func.count()).select_from(t)).scalar_one()
            for t in schema.metadata.sorted_tables
        }


def ingest(pg: Engine, s3: Any, files: list[tuple[str | None, Path]], **kw: Any) -> dict[str, Any]:
    with pg.begin() as conn:
        return ingest_files(
            conn, s3, show="demo", episode=kw.pop("episode", "S01E01"), files=files, **kw
        )


def episode_files(tmp_path: Path) -> list[tuple[str | None, Path]]:
    f = write(tmp_path, {"s.fountain": SCRIPT, "en.srt": EN, "es.srt": ES})
    return [(None, f["s.fountain"]), ("en", f["en.srt"]), ("es", f["es.srt"])]


def stub_plan() -> tuple[Plan, HardwareInventory]:
    inv = HardwareInventory(
        fingerprint="f", nodes=[], autoscaling=Autoscaling(enabled=False, max_gpu_nodes=0)
    )
    plan = Plan(
        inventory_fingerprint="f",
        catalog_sha256="c",
        objective=Objective.QUALITY,
        mode=Mode.RESIDENT,
        groups=[StageGroup(name="resident", slots=[])],
        decisions={},
    )
    return plan, inv


def test_load_timeline_equals_build_timeline(pg: Engine, s3: Any, tmp_path: Path) -> None:
    video = clip(tmp_path)
    files = [*episode_files(tmp_path), (None, video)]
    summary = ingest(pg, s3, files, picture=picture_json(tmp_path, video))
    assert [s["kind"] for s in summary["stored"]] == ["picture", "script", "subtitle", "subtitle"]
    with pg.connect() as conn:
        loaded = load_timeline(conn, "demo", "S01E01")
    script = parse("fountain", SCRIPT.encode()).data
    tracks = {k: parse("srt", v.encode()).data for k, v in [("en", EN), ("es", ES)]}
    built = build_timeline(
        "S01E01",
        script,
        probe(video),
        tracks,
        [(0, 72), (72, 144)],
        [(k["shot"], k["n"], k["frame"]) for k in KEYFRAMES],
    )
    timeline_kinds = {
        EvidenceKind.SCENE,
        EvidenceKind.SHOT,
        EvidenceKind.KEYFRAME,
        EvidenceKind.SUBTITLE_CUE,
    }
    same = tuple(s for s in loaded.spans if s.kind in timeline_kinds)
    assert loaded.model_copy(update={"spans": same}).model_dump() == built.model_dump()
    lines = loaded.of(EvidenceKind.SCRIPT_LINE)
    assert [(s.ref, s.text, s.frames) for s in lines] == [
        ("S01E01/line/1.1", "Maya enters.", None),
        ("S01E01/line/1.2", "Hello there.", None),
        ("S01E01/line/2.1", "Rain.", None),
    ]
    # content-addressed objects: the picture, the script, both tracks, the one keyframe image
    keys = sorted(k for _, k in s3.objects)
    assert len(keys) == 5 and "demo/S01E01/keyframes/0_0.jpg" in keys
    with pg.connect() as conn:
        kfs = conn.execute(select(schema.shot.c.keyframes).order_by(schema.shot.c.id)).scalars()
        assert [k[0].get("object_key") for k in kfs] == ["demo/S01E01/keyframes/0_0.jpg", None]


def test_load_without_picture_equals_build(pg: Engine, s3: Any, tmp_path: Path) -> None:
    files = episode_files(tmp_path)
    ingest(pg, s3, files[:1])  # script first, subtitles in a later call
    ingest(pg, s3, files[1:])
    with pg.connect() as conn:
        loaded = load_timeline(conn, "demo", "S01E01")
    script = parse("fountain", SCRIPT.encode()).data
    tracks = {k: parse("srt", v.encode()).data for k, v in [("en", EN), ("es", ES)]}
    built = build_timeline("S01E01", script, None, tracks)
    same = tuple(s for s in loaded.spans if s.kind is not EvidenceKind.SCRIPT_LINE)
    assert loaded.model_copy(update={"spans": same}).model_dump() == built.model_dump()


def test_reingest_creates_no_rows(pg: Engine, s3: Any, tmp_path: Path) -> None:
    files = episode_files(tmp_path)
    ingest(pg, s3, files)
    before = counts(pg)
    again = ingest(pg, s3, files)
    assert again["stored"] == [] and again["unchanged"] == ["s.fountain", "en.srt", "es.srt"]
    assert counts(pg) == before


def test_rejections_write_nothing(pg: Engine, s3: Any, tmp_path: Path) -> None:
    files = episode_files(tmp_path)
    dup = write(tmp_path, {"dup.fountain": SCRIPT.replace("#2#", "#1#")})["dup.fountain"]
    with pytest.raises(InputRejected, match=r"duplicate scene numbers \['1'\]"):
        ingest(pg, s3, [files[1], (None, dup)])
    assert sum(counts(pg).values()) == 0 and s3.objects == {}
    ingest(pg, s3, files)
    other = write(tmp_path, {"v2.fountain": SCRIPT + "\nINT. HALL - DAY #3#\n\nWalk.\n"})
    with pytest.raises(InputRejected, match="already has a script"):
        ingest(pg, s3, [(None, other["v2.fountain"])])
    with pytest.raises(InputRejected, match="already has es subtitles"):
        ingest(pg, s3, [("es", write(tmp_path, {"es2.srt": EN.replace("Bye", "Chao")})["es2.srt"])])
    with pytest.raises(InputRejected, match="--episode SxxEyy"):
        ingest(pg, s3, files[:1], episode="E1")


def test_picture_at_another_rate_after_rows_is_rejected(
    pg: Engine, s3: Any, tmp_path: Path
) -> None:
    ingest(pg, s3, episode_files(tmp_path))  # placed at 24 fps: no picture yet
    with pytest.raises(InputRejected, match="ingest the picture first"):
        ingest(pg, s3, [(None, clip(tmp_path, fps=25))])


def test_show_level_files_and_extra_refs_resolve(pg: Engine, s3: Any, tmp_path: Path) -> None:
    f = write(tmp_path, {"bible.yaml": BIBLE, "g.csv": GLOSSARY, "c.csv": CLEARANCE})
    ingest(
        pg,
        s3,
        [(None, f["bible.yaml"]), ("glossary", f["g.csv"]), ("clearance_log", f["c.csv"])],
        episode=None,
    )
    ingest(pg, s3, episode_files(tmp_path))
    e, a = schema.entity, schema.entity_alias
    with pg.begin() as conn:
        rows = conn.execute(
            select(e.c.kind, e.c.canonical_name, e.c.fictional, e.c.origin).order_by(e.c.id)
        ).all()
        assert [tuple(r) for r in rows] == [
            ("character", "Maya Reyes", None, "bible"),
            ("secret", "maya_is_informant", None, "bible"),
            ("brand", "Kappa Cola", True, "bible"),
            ("location", "Harbor Warehouse", True, "bible"),
            ("term", "the Hollow", None, "glossary"),
        ]
        aliases = {tuple(r) for r in conn.execute(select(a.c.lang, a.c.alias, a.c.kind))}
        assert {("any", "May", "nickname"), ("es", "el Hueco", "approved_rendering")} <= aliases
        # a fact citing line 1.2 (fact_event -> fact), as 2.1 will write them
        maya = conn.execute(select(e.c.id).where(e.c.kind == "character")).scalar_one()
        line = conn.execute(
            select(schema.script_line.c.id, schema.script_line.c.scene_id).where(
                schema.script_line.c.seq == 2
            )
        ).one()
        ev = conn.execute(
            insert(schema.fact_event)
            .values(
                scene_id=line.scene_id,
                line_id=line.id,
                predicate="present_at",
                subject_id=maya,
                quote="Hello there",
                confidence=0.9,
            )
            .returning(schema.fact_event.c.id)
        ).scalar_one()
        conn.execute(
            insert(schema.fact).values(
                show_id=conn.execute(select(schema.show.c.id)).scalar_one(),
                predicate="present_at",
                subject_id=maya,
                screen=text("int8range(0, 10)"),
                story=text("int4range(1, 2)"),
                source_event_ids=[ev],
                confidence=0.9,
            )
        )
        tl = load_timeline(conn, "demo", "S01E01")
    fact = tl.resolve("fact/1")
    assert fact is not None and fact.kind is EvidenceKind.FACT and fact.text == "Hello there"
    clr = tl.resolve("clr/1")
    assert clr is not None and clr.text == "Acme Hardware" and clr.frames is None
    # a revised glossary replaces the approved rendering; re-ingesting adds no entity
    g2 = write(tmp_path, {"g2.csv": GLOSSARY.replace("el Hueco", "la Hondonada")})["g2.csv"]
    ingest(pg, s3, [("glossary", g2)], episode=None)
    with pg.connect() as conn:
        renderings = conn.execute(select(a.c.alias).where(a.c.kind == "approved_rendering"))
        assert renderings.scalars().all() == ["la Hondonada"]
        assert conn.execute(select(func.count()).select_from(e)).scalar_one() == 5


def test_run_persists_flags_with_stable_fingerprints(pg: Engine, s3: Any, tmp_path: Path) -> None:
    ingest(pg, s3, episode_files(tmp_path))
    plan, inv = stub_plan()
    out = tmp_path / "out"
    first = pipeline.run_store(
        pg, s3, show="demo", episodes=["S01E01"], plan=plan, inventory=inv, out_dir=out
    )
    pipeline.run_store(pg, s3, show="demo", episodes=["S01E01"], plan=plan, inventory=inv)
    assert (first["run_id"], first["status"], first["agents"]) == (
        "run_1",
        "completed",
        ["localization_auditor"],
    )
    ep = first["episodes"]["S01E01"]
    assert ep["flags_kept"] == 2 and ep["units"] == {"done": 3} and ep["dropped"] == []
    assert [s["stage"] for s in ep["stages"]] == [n for n, _ in pipeline.STAGES]
    f, ev, r, wu = schema.flag, schema.evidence, schema.run, schema.work_unit
    with pg.connect() as conn:
        by_run = conn.execute(select(f.c.run_id, f.c.fingerprint).order_by(f.c.id)).all()
        assert [fp for run, fp in by_run if run == 1] == [fp for run, fp in by_run if run == 2]
        runs = conn.execute(
            select(r.c.status, r.c.previous_run_id, r.c.plan_id, r.c.code_version).order_by(r.c.id)
        ).all()
        assert [(s, p, pl) for s, p, pl, _ in runs] == [("completed", None, 1), ("completed", 1, 2)]
        assert len(runs[0].code_version.removesuffix("-dirty")) == 40  # git SHA (+ dirty tree)
        assert conn.execute(
            select(wu.c.stage, wu.c.unit_key, wu.c.status).where(wu.c.run_id == 1)
        ).all() == [
            ("loc.readability", "S01E01/es/1-3", "done"),
            ("loc.drift", "S01E01/es/sync", "done"),
            ("loc.offset", "S01E01/es/sync", "done"),
        ]
        n_ev = conn.execute(select(func.count()).select_from(ev)).scalar_one()
        assert n_ev == 6  # (claim) + (claim + earlier cue as context), in each of the 2 runs
    report = json.loads(s3.objects["nip-artifacts", "runs/run_1/S01E01/report.json"])
    loc = next(s for s in report["sections"] if s["category"] == "localization")
    assert [x["id"] for x in loc["flags"]] == ["flg_1", "flg_2"]
    assert report["plan"]["plan_id"] == "plan_1" and report["coverage"] == {
        "localization_auditor": 1.0
    }
    assert ("nip-artifacts", "runs/run_1/plan.json") in s3.objects
    # every kept flag's evidence resolves against the stored timeline
    flags = [json.loads(x) for x in (out / "S01E01" / "flags.jsonl").read_text().splitlines()]
    with pg.connect() as conn:
        tl = load_timeline(conn, "demo", "S01E01")
    for fl in flags:
        assert fl["verification"] == {
            "evidence": "pass",
            "rule_recheck": "pass",
            "judge": "n/a",
            "judge_variant": None,
        }
        assert all(tl.resolve(e["ref"]) for e in fl["evidence"])


def test_failed_unit_is_a_gap_and_a_crash_fails_the_run(
    pg: Engine, s3: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingest(pg, s3, episode_files(tmp_path))
    plan, inv = stub_plan()

    def boom(*_: Any) -> Any:
        raise RuntimeError("boom")

    from nip.agents.localization.readability import Readability

    monkeypatch.setattr(Readability, "run", boom)
    s = pipeline.run_store(pg, s3, show="demo", episodes=["S01E01"], plan=plan, inventory=inv)
    assert s["status"] == "completed_with_gaps" and s["episodes"]["S01E01"]["units"] == {
        "failed": 1,
        "done": 2,  # loc.drift and loc.offset
    }
    report = json.loads(s3.objects["nip-artifacts", "runs/run_1/S01E01/report.json"])
    assert report["status"] == "completed_with_gaps"
    assert report["coverage"] == {"localization_auditor": 2 / 3}  # 1 of 3 units failed

    monkeypatch.setattr(pipeline, "STAGES", [*pipeline.STAGES[:1], ("crash", boom)])
    with pytest.raises(RuntimeError, match="boom"):
        pipeline.run_store(pg, s3, show="demo", episodes=["S01E01"], plan=plan, inventory=inv)
    with pg.connect() as conn:
        assert (
            conn.execute(select(schema.run.c.status).where(schema.run.c.id == 2)).scalar_one()
            == "failed"
        )
    with pytest.raises(InputRejected, match="no episode S01E09"):
        pipeline.run_store(pg, s3, show="demo", episodes=["S01E09"], plan=plan, inventory=inv)


def test_scene_label_gives_way_to_timecodes_on_a_picture_timeline(
    pg: Engine, s3: Any, tmp_path: Path
) -> None:
    ingest(pg, s3, episode_files(tmp_path))
    with pg.begin() as conn:
        conn.execute(update(schema.episode).values(timeline_source="picture"))
        tl = load_timeline(conn, "demo", "S01E01")
    sc = tl.resolve("S01E01/sc/1")
    assert (
        tl.source == "picture" and sc is not None and sc.scene is None and sc.tc_in == "00:00:00:00"
    )


def test_cli_ingest_and_run(
    pg: Engine, s3: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NIP_DATABASE_URL", pg.url.render_as_string(hide_password=False))
    monkeypatch.setattr(objects, "client", lambda: s3)
    monkeypatch.setattr(pipeline, "current_plan", lambda workload: stub_plan())
    files = [f"{t}={p}" if t else str(p) for t, p in episode_files(tmp_path)]
    runner = CliRunner()
    res = runner.invoke(app, ["ingest", "--show", "demo", "--episode", "S01E01", *files])
    assert res.exit_code == 0, res.output
    assert [s["source_id"] for s in json.loads(res.output)["stored"]] == ["src_1", "src_2", "src_3"]
    res = runner.invoke(
        app, ["ingest", "--show", "demo", "--episode", "S01E01", str(tmp_path / "es.srt")]
    )
    assert (
        res.exit_code == 1 and "INPUT_REJECTED: es.srt: give subtitles as LANG=PATH" in res.output
    )
    res = runner.invoke(app, ["run", "--show", "demo", "--episodes", "S01E01"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["episodes"]["S01E01"]["flags_kept"] == 2
    res = runner.invoke(app, ["run", "--show", "demo", "--episodes", "S01E02"])
    assert res.exit_code == 1 and "INPUT_REJECTED: no episode S01E02" in res.output


def test_content_stage_records_units_once_and_a_failed_unit_is_a_gap(
    pg: Engine, s3: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingest(pg, s3, episode_files(tmp_path))
    plan, inv = stub_plan()
    seen: list[str | None] = []

    def extract(ep: pipeline.EpisodeRun) -> None:  # a 2.1-style content stage, one unit per scene
        seen.append(ep.plan.plan_id)
        for no in ("1", "2"):
            with ep.unit("knowledge.extract", f"{ep.episode}/sc/{no}", model_variant="stub"):
                if no == "2":
                    raise TimeoutError("model timed out")

    monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
    pipeline.add_stage("knowledge.extract", extract)
    out = tmp_path / "out"
    s = pipeline.run_store(
        pg, s3, show="demo", episodes=["S01E01"], plan=plan, inventory=inv, out_dir=out
    )
    assert seen == ["plan_1"] and s["status"] == "completed_with_gaps"
    assert s["episodes"]["S01E01"]["flags_kept"] == 2  # the gap does not stop the checks
    wu = schema.work_unit
    with pg.connect() as conn:
        rows = conn.execute(
            select(wu.c.stage, wu.c.unit_key, wu.c.status, wu.c.model_variant, wu.c.error).order_by(
                wu.c.id
            )
        ).all()
    assert [tuple(r) for r in rows] == [  # each unit once
        ("knowledge.extract", "S01E01/sc/1", "done", "stub", None),
        ("knowledge.extract", "S01E01/sc/2", "failed", "stub", "TimeoutError: model timed out"),
        ("loc.readability", "S01E01/es/1-3", "done", None, None),
        ("loc.drift", "S01E01/es/sync", "done", None, None),
        ("loc.offset", "S01E01/es/sync", "done", None, None),
    ]
    report = json.loads(s3.objects["nip-artifacts", "runs/run_1/S01E01/report.json"])
    assert report["status"] == "completed_with_gaps"
    assert report["coverage"] == {"localization_auditor": 1.0}  # content units: no agent


def test_failed_run_publishes_no_artifacts(
    pg: Engine, s3: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingest(pg, s3, episode_files(tmp_path))
    before = dict(s3.objects)
    plan, inv = stub_plan()

    def crash(ep: pipeline.EpisodeRun) -> None:
        raise ConnectionError("lost the database")

    monkeypatch.setattr(pipeline, "STAGES", [*pipeline.STAGES, ("crash", crash)])  # after report
    out = tmp_path / "out"
    with pytest.raises(ConnectionError):
        pipeline.run_store(
            pg, s3, show="demo", episodes=["S01E01"], plan=plan, inventory=inv, out_dir=out
        )
    assert s3.objects == before and not out.exists()
    with pg.connect() as conn:
        assert conn.execute(select(func.count()).select_from(schema.flag)).scalar_one() == 0
        assert conn.execute(select(schema.run.c.status)).scalar_one() == "failed"


def test_flag_citing_only_facts_is_dropped(
    pg: Engine, s3: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingest(pg, s3, episode_files(tmp_path))
    plan, inv = stub_plan()

    def fact_only(ep: pipeline.EpisodeRun) -> None:
        ep.flags.append(
            Flag.model_validate({
                "run_id": ep.run_id, "episode": ep.episode, "agent": "script_critic",
                "check": "plot.knowledge_order", "category": "plot_hole", "severity": 4,
                "confidence": 0.9, "tier": "must_review", "title": "refers before learning",
                "explanation": "e", "produced_by": {"model_variant": None, "plan_id": "p"},
                "evidence": [{"kind": "fact", "ref": "fact/7", "role": "claim"}],
            })
        )  # fmt: skip

    monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
    pipeline.add_stage("plot", fact_only, before="verification")
    s = pipeline.run_store(pg, s3, show="demo", episodes=["S01E01"], plan=plan, inventory=inv)
    ep = s["episodes"]["S01E01"]
    assert ep["flags_kept"] == 2 and ep["dropped"] == [
        {"title": "refers before learning",
         "reason": "no stable evidence ref (scene/line/shot/kf/cue/clr), R13"}
    ]  # fmt: skip


def test_failed_unit_rolls_back_its_rows_and_does_not_poison_the_next(
    pg: Engine, s3: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingest(pg, s3, episode_files(tmp_path))
    plan, inv = stub_plan()
    sc = schema.scene

    def story(ep: pipeline.EpisodeRun) -> None:  # a 2.2-style writer, one unit per scene
        with ep.unit("knowledge.story", "S01E01/sc/1"):  # writes, then fails: rows rolled back
            ep.conn.execute(update(sc).where(sc.c.script_scene_no == "1").values(story_seq=1))
            raise RuntimeError("bad transition")
        with ep.unit("knowledge.story", "S01E01/sc/2"):  # a database error
            ep.conn.execute(text("SELECT 1/0"))
        with ep.unit("knowledge.story", "S01E01/sc/3"):  # still runs on a healthy transaction
            ep.conn.execute(update(sc).where(sc.c.script_scene_no == "2").values(story_seq=2))

    monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
    pipeline.add_stage("knowledge.story", story)
    s = pipeline.run_store(pg, s3, show="demo", episodes=["S01E01"], plan=plan, inventory=inv)
    assert s["status"] == "completed_with_gaps"
    assert s["episodes"]["S01E01"]["units"] == {"failed": 2, "done": 4}
    assert s["episodes"]["S01E01"]["flags_kept"] == 2
    with pg.connect() as conn:
        seqs = conn.execute(select(sc.c.script_scene_no, sc.c.story_seq).order_by(sc.c.id)).all()
        errors = (
            conn.execute(select(schema.work_unit.c.error).order_by(schema.work_unit.c.id))
            .scalars()
            .all()
        )
    assert [tuple(r) for r in seqs] == [("1", None), ("2", 2)]
    assert errors[0] == "RuntimeError: bad transition" and "DivisionByZero" in errors[1]
    assert errors[2:] == [None] * 4
