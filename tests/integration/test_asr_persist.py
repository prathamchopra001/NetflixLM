"""The `timeline.asr` and `timeline.align` store-mode stages, run through `pipeline.run_store`.

A 6 s clip with a sine track is ingested with a script and a cached picture.json; a stub ASR backend
returns canned segments. The stages store transcript segments, then place lines and scenes and set
`episode.timeline_source = 'picture'`.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select

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
from nip.contracts.flag import EvidenceKind
from nip.runtime.clients.asr import Segment, StubASR, Word
from nip.store import schema
from nip.store.ingest import ingest_files
from nip.store.load import load_timeline
from nip.timeline import align, asr

pytestmark = pytest.mark.integration

SCRIPT = (
    "INT. ROOM - DAY\n\nMAYA\nHello there my dear friend.\n\n"
    "EXT. DOCK - NIGHT\n\nBOB\nThis long speech never happens anywhere in the cut at all.\n"
)


class DownloadingS3:
    """The conftest S3 stand-in plus `download_file`, which `timeline.asr` calls."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        Path(filename).write_bytes(self.inner.objects[bucket, key])


def plan(asked: bool) -> tuple[Plan, HardwareInventory]:
    inv = HardwareInventory(
        fingerprint="f", nodes=[], autoscaling=Autoscaling(enabled=False, max_gpu_nodes=0)
    )
    decisions = {Slot.ASR: SlotDecision(variant="stub-asr")} if asked else {}
    p = Plan(
        inventory_fingerprint="f",
        catalog_sha256="c",
        objective=Objective.QUALITY,
        mode=Mode.RESIDENT,
        groups=[StageGroup(name="resident", slots=[])],
        decisions=decisions,
    )
    return p, inv


@pytest.fixture
def ingested(pg: Engine, s3: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not on PATH")
    video = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=64x64:rate=24:duration=6",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=6",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(video),
        ],
        check=True,
    )
    pic = tmp_path / "picture.json"
    pic.write_text(
        json.dumps(
            {
                "fps": [24, 1],
                "duration_frames": 144,
                "start_tc_frames": 0,
                "drop_frame": False,
                "shots": [[0, 72], [72, 144]],
                "keyframes": [],
            }
        )
    )
    script = tmp_path / "s.fountain"
    script.write_text(SCRIPT, encoding="utf-8")
    store = DownloadingS3(s3)
    with pg.begin() as conn:
        ingest_files(
            conn,
            store,
            show="demo",
            episode="S01E01",
            files=[(None, video), (None, script)],
            picture=pic,
        )
    monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
    pipeline.add_stage("timeline.asr", asr.stage)
    pipeline.add_stage("timeline.align", align.stage)
    return store


def canned(monkeypatch: pytest.MonkeyPatch) -> None:
    words = tuple(
        Word(w, 1000 + i * 300, 1300 + i * 300, 0.9)
        for i, w in enumerate("hello there my dear friend".split())
    )
    seg = Segment("hello there my dear friend", 1000, 2500, words)
    noise = Segment("background", 4000, 4500, (Word("background", 4000, 4500, 0.9),))
    monkeypatch.setattr(asr, "backend", lambda variant: StubASR(variant, (seg, noise)))


def run(pg: Engine, store: Any, asked: bool = True) -> dict[str, Any]:
    p, inv = plan(asked)
    return pipeline.run_store(pg, store, show="demo", episodes=["S01E01"], plan=p, inventory=inv)


def test_stages_store_the_transcript_and_place_lines_and_scenes(
    pg: Engine, ingested: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    canned(monkeypatch)
    summary = run(pg, ingested)
    assert summary["status"] == "completed"
    with pg.connect() as c:
        wu = c.execute(
            select(
                schema.work_unit.c.stage,
                schema.work_unit.c.model_variant,
                schema.work_unit.c.status,
            ).order_by(schema.work_unit.c.id)
        ).all()
        scenes = c.execute(
            select(schema.scene.c.frames, schema.scene.c.in_cut).order_by("id")
        ).all()
        lines = c.execute(
            select(schema.script_line.c.kind, schema.script_line.c.frames).order_by("id")
        ).all()
        segs = c.execute(
            select(
                schema.transcript_segment.c.frames,
                schema.transcript_segment.c.words,
                schema.transcript_segment.c.aligned_line_id,
            ).order_by("id")
        ).all()
        source = c.execute(select(schema.episode.c.timeline_source)).scalar_one()
        tl = load_timeline(c, "demo", "S01E01")
    assert [tuple(r) for r in wu] == [
        ("timeline.asr", "stub-asr", "done"),
        ("timeline.align", None, "done"),
    ]
    assert source == "picture"
    assert (lines[0].frames.lower, lines[0].frames.upper) == (24, 60)  # 1.0 s .. 2.5 s at 24 fps
    assert lines[1].frames is None
    assert (scenes[0].frames.lower, scenes[0].frames.upper) == (0, 72) and scenes[0].in_cut
    assert scenes[1].frames is None and not scenes[1].in_cut
    assert segs[0].words[0] == {"w": "hello", "f_in": 24, "f_out": 31, "p": 0.9}
    assert segs[0].aligned_line_id is not None and segs[1].aligned_line_id is None
    sc1, sc2 = tl.of(EvidenceKind.SCENE)
    assert sc1.tc_in == "00:00:00:00" and sc1.scene is None  # SMPTE, not the estimate label
    assert sc2.frames is None


def test_no_asr_decision_or_a_failing_backend_leaves_the_estimate(
    pg: Engine, ingested: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run(pg, ingested, asked=False)["status"] == "completed"

    def boom(variant: str) -> StubASR:
        raise RuntimeError("no CUDA")

    monkeypatch.setattr(asr, "backend", boom)
    assert run(pg, ingested)["status"] == "completed_with_gaps"
    with pg.connect() as c:
        n = c.execute(select(schema.transcript_segment.c.id)).all()
        src = c.execute(select(schema.episode.c.timeline_source)).scalar_one()
        failed = c.execute(
            select(schema.work_unit.c.stage, schema.work_unit.c.error).where(
                schema.work_unit.c.status == "failed"
            )
        ).all()
    assert n == [] and src == "script_estimate"
    assert [r.stage for r in failed] == ["timeline.asr"] and "no CUDA" in failed[0].error


def test_a_script_only_episode_with_an_asr_decision_records_no_unit(
    pg: Engine, s3: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """W-int: `nip run` asks for an asr slot for every run; a script-only episode is not a gap."""
    script = tmp_path / "s.fountain"
    script.write_text(SCRIPT, encoding="utf-8")
    with pg.begin() as conn:
        ingest_files(conn, s3, show="demo", episode="S01E01", files=[(None, script)])
    monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
    pipeline.add_stage("timeline.asr", asr.stage)
    pipeline.add_stage("timeline.align", align.stage)
    s = run(pg, s3)
    assert s["status"] == "completed"
    assert not [u for u in s["episodes"]["S01E01"]["units"] if u != "done"]
    with pg.connect() as c:
        assert c.execute(select(schema.work_unit.c.stage)).scalars().all() == []
