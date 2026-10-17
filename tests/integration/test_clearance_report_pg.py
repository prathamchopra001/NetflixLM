"""Clearance end to end through the store (R15: needs NIP_TEST_DATABASE_URL and ffmpeg): ingest a
clip with rendered keyframes and a clearance log, run the wired OCR stage (recorded reader) and the
six checks, then read flags, detection rows, crops, the CSV artifact and `nip clearance report`."""

import importlib.util
import io
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import Engine, func, select
from typer.testing import CliRunner

from nip import pipeline
from nip.agents import clearance
from nip.agents.clearance import report, stage
from nip.agents.clearance.stage import STAGE
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
from nip.ingest.media import probe
from nip.runtime.clients.ocr import OcrLine, StubOCR, fingerprint
from nip.store import objects, schema
from nip.store.ingest import ingest_files

pytestmark = pytest.mark.integration

FIX = Path(__file__).parents[1] / "fixtures" / "clearance"
spec = importlib.util.spec_from_file_location("clr_render", FIX / "render.py")
assert spec and spec.loader
render_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_mod)

CLEARANCE = (
    "item,kind,status,scope,notes\n"
    "(212) 555-0234,phone,pending,,legal\n"
    "(415) 555-2671,phone,cleared,,licensed\n"
    "Veltrix Cola,brand,denied,,no\n"
)
BIBLE = "show: demo\ncharacters: []\nfictional:\n  brands: [Kappa Cola]\n"
BOX = (0.1, 0.2, 0.4, 0.06)
# shot 0 [0, 72): a pending and a cleared number; shot 1 [72, 144): a number not in the log, the
# denied brand, and the fictional brand
LINES = {
    0: ["CALL (212) 555-0234", "(415) 555-2671"],
    1: ["(617) 482-9154", "VELTRIX COLA", "KAPPA COLA"],
}


def jpeg(lines: list[str]) -> bytes:
    out = io.BytesIO()
    Image.open(io.BytesIO(render_mod.render(lines))).convert("RGB").save(out, "JPEG", quality=95)
    return out.getvalue()


@pytest.fixture
def setup(pg: Engine, s3: Any, tmp_path: Path) -> tuple[StubOCR, Path]:
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not on PATH")
    video = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "testsrc2=size=160x90:rate=24:duration=6",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
        check=True,
    )  # fmt: skip
    (tmp_path / "keyframes").mkdir()
    recorded = {}
    for shot in (0, 1):
        data = jpeg(LINES[shot])
        (tmp_path / "keyframes" / f"{shot}_0.jpg").write_bytes(data)
        recorded[fingerprint(data)] = [
            OcrLine(text=t, box=(BOX[0], BOX[1] + 0.1 * i, BOX[2], BOX[3]), confidence=0.96)
            for i, t in enumerate(LINES[shot])
        ]
    m = probe(video)
    pic = {"fps": [m.fps.numerator, m.fps.denominator], "duration_frames": m.duration_frames,
           "start_tc_frames": 0, "drop_frame": False, "shots": [[0, 72], [72, 144]],
           "keyframes": [{"shot": 0, "n": 0, "frame": 36, "file": "0_0.jpg"},
                         {"shot": 1, "n": 0, "frame": 108, "file": "1_0.jpg"}]}  # fmt: skip
    (tmp_path / "picture.json").write_text(json.dumps(pic), encoding="utf-8")
    (tmp_path / "c.csv").write_text(CLEARANCE, encoding="utf-8")
    (tmp_path / "bible.yaml").write_text(BIBLE, encoding="utf-8")
    with pg.begin() as conn:
        ingest_files(conn, s3, show="demo", episode=None, files=[
            (None, tmp_path / "bible.yaml"), ("clearance_log", tmp_path / "c.csv")])  # fmt: skip
    with pg.begin() as conn:
        ingest_files(conn, s3, show="demo", episode="S01E01", files=[(None, video)],
                     picture=tmp_path / "picture.json")  # fmt: skip
    return StubOCR(recorded), tmp_path


def plan() -> tuple[Plan, HardwareInventory]:
    inv = HardwareInventory(
        fingerprint="f", nodes=[], autoscaling=Autoscaling(enabled=False, max_gpu_nodes=0)
    )
    decisions = {s: SlotDecision(variant="stub") for s in (Slot.OCR, Slot.NER)}
    p = Plan(
        inventory_fingerprint="f", catalog_sha256="c", objective=Objective.QUALITY,
        mode=Mode.RESIDENT, groups=[StageGroup(name="resident", slots=[])], decisions=decisions,
    )  # fmt: skip
    return p, inv


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch, setup: tuple[StubOCR, Path]) -> None:
    monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
    monkeypatch.setattr(pipeline, "AGENTS", [clearance])
    pipeline.add_stage(STAGE, stage.stage, before="checks")
    pipeline.add_stage("clearance.csv", report.stage, before="report")
    monkeypatch.setattr(stage, "ocr_reader", lambda variant: setup[0])


def run(pg: Engine, s3: Any) -> dict[str, Any]:
    p, inv = plan()
    return pipeline.run_store(pg, s3, show="demo", episodes=["S01E01"], plan=p, inventory=inv)


def test_flags_detections_crops_and_csv(
    pg: Engine, s3: Any, wired: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary = run(pg, s3)
    ep = summary["episodes"]["S01E01"]
    assert summary["status"] == "completed" and ep["dropped"] == []
    order = [s["stage"] for s in ep["stages"]]
    assert order.index(STAGE) < order.index("checks") < order.index("flags")
    assert order.index("flags") < order.index("clearance.csv") < order.index("report")
    f, ev, d = schema.flag, schema.evidence, schema.detection
    with pg.connect() as conn:
        flags = conn.execute(select(f.c.check_id, f.c.tier, f.c.severity, f.c.title)).all()
        got = {
            next(
                t for t in ("212", "415", "617", "Veltrix", "Kappa") if t.lower() in r.title.lower()
            ): r  # noqa: E501
            for r in flags
        }
        # pending: must_review sev 4; cleared: suppressed (kept for the audit); the denied brand:
        # must_review sev 5; a number outside the log: severity by prominence; Kappa Cola: no flag
        assert (got["212"].tier, got["212"].severity) == ("must_review", 4)
        assert got["415"].tier == "suppressed"
        assert (got["Veltrix"].tier, got["Veltrix"].severity) == ("must_review", 5)
        assert got["617"].severity in (2, 4) and "Kappa" not in got and len(flags) == 4
        labels = conn.execute(select(d.c.label, func.count()).group_by(d.c.label)).all()
        counts = {r[0]: r[1] for r in labels}
        assert (
            counts["text"] == 5
            and counts["sharpness"] == counts["clr.phone"] + counts["clr.brand_text"]
        )
        assert conn.execute(select(func.count()).select_from(ev)).scalar_one() >= 4
        claims = conn.execute(
            select(ev.c.ref, ev.c.frames).where(ev.c.role == "claim")
        ).all()  # the claim of every flag is its occurrence: a `clr/occ-` span with the range
        assert len(claims) == len(flags) and all(
            c.ref.startswith("clr/occ-") and c.frames is not None for c in claims
        )
        crops = [k for _, k in s3.objects if k.startswith("demo/S01E01/crops/")]
        n_cand = conn.execute(
            select(func.count()).select_from(d).where(d.c.label.like("clr.%"))
        ).scalar_one()
        assert len(crops) == n_cand == 4
    rows = report.from_csv(
        s3.objects["nip-artifacts", "runs/run_1/S01E01/clearance_report.csv"].decode()
    )
    assert [(r["item"], r["status"]) for r in rows] == [
        ("(212) 555-0234", "pending"), ("Veltrix Cola", "denied"), ("(617) 482-9154", "unknown"),
    ]  # fmt: skip
    assert all(r["flag_id"].startswith("flg_") and r["thumbnail_url"] for r in rows)
    # a second run replaces the detection rows instead of adding to them
    run(pg, s3)
    with pg.connect() as conn:
        assert conn.execute(select(func.count()).select_from(d)).scalar_one() == sum(
            counts.values()
        )
    # the CLI reads the same report from the store; cleared occurrences only with --include-hidden
    monkeypatch.setenv("NIP_DATABASE_URL", pg.url.render_as_string(hide_password=False))
    res = CliRunner().invoke(
        report.app, ["report", "--show", "demo", "--episode", "S01E01", "--include-hidden"]
    )
    assert res.exit_code == 0, res.output
    cli_rows = report.from_csv(res.output)
    assert [r["status"] for r in cli_rows] == ["pending", "cleared", "denied", "unknown"]
    assert cli_rows[0]["flag_id"].startswith("flg_") and cli_rows[1]["flag_id"].startswith("flg_")


def test_an_unreadable_keyframe_is_a_gap_and_the_others_still_count(
    pg: Engine, s3: Any, wired: None
) -> None:
    del s3.objects[objects.media_bucket(), "demo/S01E01/keyframes/1_0.jpg"]
    summary = run(pg, s3)
    assert summary["status"] == "completed_with_gaps"
    wu = schema.work_unit
    with pg.connect() as conn:
        units = conn.execute(select(wu.c.unit_key, wu.c.status).where(wu.c.stage == STAGE)).all()
        assert sorted(tuple(u) for u in units) == [
            ("S01E01/kf/0.0", "done"),
            ("S01E01/kf/1.0", "failed"),
        ]
        checks = conn.execute(select(schema.flag.c.check_id)).scalars().all()
    assert sorted(checks) == ["clr.phone", "clr.phone"]  # shot 0's pending and cleared numbers
