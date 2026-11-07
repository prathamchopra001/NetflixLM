import json
import shutil
import subprocess
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from eval.labeling.labeling import (
    VERIFY,
    app,
    clip_offset,
    common_fps,
    ls_framerate,
    make_clips,
    make_tasks,
    make_verify_clip,
    parse_cuts,
    probe_fps,
    render_config,
)

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


def test_framerate_strings() -> None:
    assert ls_framerate((24, 1)) == "24"
    assert ls_framerate((24000, 1001)) == "23.976023976"  # never "24000/1001"
    assert 'framerate="23.976023976"' in render_config((24000, 1001))
    assert "{" not in render_config((24, 1))


def test_offsets_and_tasks() -> None:
    assert [clip_offset(k) for k in (0, 1, 2)] == [0, 1439, 2879]
    tasks = make_tasks("sintel", [Path("sintel_000.mp4"), Path("sintel_001.mp4")], "24/1")
    assert [t["data"]["clip"] for t in tasks] == [VERIFY, "sintel_000.mp4", "sintel_001.mp4"]
    assert tasks[0]["data"]["verify"] is True
    assert tasks[2]["data"] == {
        "video": "/data/local-files/?d=labeling/sintel/sintel_001.mp4",
        "offset_frames": 1439,
        "clip": "sintel_001.mp4",
        "fps": "24/1",
    }


def ann(clip: str, offset: int, frames: list[int], **kw: object) -> dict[str, Any]:
    result = [
        {"value": {"ranges": [{"start": f, "end": f}], "timelinelabels": ["Cut"]}} for f in frames
    ]
    return {
        "data": {"offset_frames": offset, "clip": clip, "fps": "24/1"},
        "annotations": [{"result": result, **kw}],
    }


def unlabelled(clip: str, offset: int) -> dict[str, Any]:
    return {"data": {"offset_frames": offset, "clip": clip, "fps": "24/1"}, "annotations": []}


def test_parse_cuts() -> None:
    tasks = [
        {"data": {"verify": True, "clip": VERIFY, "offset_frames": 0, "fps": "24/1"}},
        ann("a", 0, [10, 5, 1]),  # frame 1 of clip 0 is never a cut
        ann("b", 1439, [1, 2, 100]),  # frame 1 is the overlap frame; 2 -> global 1440
        ann("c", 2879, [1], was_cancelled=True),  # cancelled -> counts as unlabelled
        unlabelled("d", 4319),
    ]
    cuts, missing = parse_cuts(tasks)
    assert cuts == [4, 9, 1440, 1538]
    assert missing == ["c", "d"]


def test_parse_cuts_latest_annotation_wins() -> None:
    t = ann("a", 0, [3], updated_at="2026-01-01")
    t["annotations"].append(ann("a", 0, [7], updated_at="2026-02-01")["annotations"][0])
    assert parse_cuts([t]) == ([6], [])


def ffmpeg_clip(dst: Path, rate: str, frames: int = 30) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         f"testsrc2=size=160x90:rate={rate}:duration=2", "-frames:v", str(frames),
         "-c:v", "libx264", "-video_track_timescale", "24000000", str(dst)],
        check=True,
    )  # fmt: skip


@needs_ffmpeg
def test_verify_clip_ntsc_rate(tmp_path: Path) -> None:
    out = tmp_path / "v.mp4"
    make_verify_clip(out, (24000, 1001), seconds=2)
    assert probe_fps(out) == (24000, 1001)


@needs_ffmpeg
def test_common_fps_refuses_mixed_rates(tmp_path: Path) -> None:
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    ffmpeg_clip(a, "24")
    ffmpeg_clip(b, "24000/1001")
    assert common_fps([a]) == (24, 1)
    with pytest.raises(ValueError, match="one frame rate"):
        common_fps([a, b])


@needs_ffmpeg
def test_make_clips_frame_counts(tmp_path: Path) -> None:
    src = tmp_path / "film.mkv"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=5",
         "-c:v", "libx264", str(src)],
        check=True,
    )  # fmt: skip
    clips = make_clips(src, tmp_path / "clips", 120, clip_frames=50, width=160)
    counts = [
        int(
            subprocess.run(
                ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                 "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(c)],
                check=True, capture_output=True, text=True,
            ).stdout
        )
        for c in clips
    ]  # fmt: skip
    assert counts == [50, 51, 21]  # clips after the first start one frame early (overlap)


class Fake(BaseHTTPRequestHandler):
    calls: list[tuple[str, str, Any, str | None]] = []
    export: list[dict[str, Any]] = []

    def _do(self) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n)) if n else None
        Fake.calls.append((self.command, self.path, body, self.headers.get("Authorization")))
        out: Any = {"id": 7} if self.path == "/api/projects" else {}
        if "/export" in self.path:
            out = Fake.export
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_POST = do_GET = _do

    def log_message(self, *a: object) -> None:
        pass


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    Fake.calls, Fake.export = [], []
    srv = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("LABEL_STUDIO_TOKEN", "abc")
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def make_dir(tmp_path: Path, rates: list[str]) -> Path:
    d = tmp_path / "labeling" / "sintel"
    d.mkdir(parents=True)
    for k, r in enumerate(rates):
        ffmpeg_clip(d / f"sintel_{k:03d}.mp4", r)
    ffmpeg_clip(d / VERIFY, rates[0])
    return tmp_path


@needs_ffmpeg
@pytest.mark.parametrize(("rate", "config_rate"), [("24", "24"), ("24000/1001", "23.976023976")])
def test_push_probes_clips_and_puts_verify_first(
    tmp_path: Path, server: str, rate: str, config_rate: str
) -> None:
    data = make_dir(tmp_path, [rate, rate])
    r = CliRunner().invoke(app, ["push", "--url", server, "--data-dir", str(data)])
    assert r.exit_code == 0, r.output
    assert [(c[0], c[1]) for c in Fake.calls] == [
        ("POST", "/api/projects"),
        ("POST", "/api/storages/localfiles"),
        ("POST", "/api/projects/7/import"),
    ]
    assert f'framerate="{config_rate}"' in Fake.calls[0][2]["label_config"]
    assert Fake.calls[0][3] == "Token abc"
    tasks = Fake.calls[2][2]
    assert [t["data"]["clip"] for t in tasks] == [VERIFY, "sintel_000.mp4", "sintel_001.mp4"]
    assert {t["data"]["fps"] for t in tasks} == {rate if "/" in rate else f"{rate}/1"}


@needs_ffmpeg
def test_push_refuses_mixed_rates_and_config_prints(tmp_path: Path, server: str) -> None:
    data = make_dir(tmp_path, ["24", "24000/1001"])
    r = CliRunner().invoke(app, ["push", "--url", server, "--data-dir", str(data)])
    assert r.exit_code != 0 and Fake.calls == []
    ok = make_dir(tmp_path / "ok", ["24000/1001"])
    r = CliRunner().invoke(app, ["config", "--data-dir", str(ok)])
    assert 'framerate="23.976023976"' in r.output


def test_push_without_prepare_fails(tmp_path: Path, server: str) -> None:
    r = CliRunner().invoke(app, ["push", "--url", server, "--data-dir", str(tmp_path)])
    assert r.exit_code != 0 and "prepare" in r.output


def pull(server: str, out: Path, *args: str) -> Any:
    return CliRunner().invoke(app, ["pull", "7", "--url", server, "--out-dir", str(out), *args])


def test_pull_writes_documented_format(tmp_path: Path, server: str) -> None:
    Fake.export = [ann("sintel_000.mp4", 0, [35]), ann("sintel_001.mp4", 1439, [1, 2])]
    r = pull(server, tmp_path)
    assert r.exit_code == 0, r.output
    assert "2/2 clips labelled" in r.output
    doc = json.loads((tmp_path / "sintel_cuts.json").read_text())
    assert doc["cuts"] == [34, 1440]
    assert doc["fps"] == "24/1" and doc["labeller"] == "human" and doc["unlabelled_clips"] == []
    assert doc["title"] == "sintel" and doc["check"] == "shot.cut"
    assert "first frame of the new shot" in doc["frame_convention"]


def test_pull_fails_on_unlabelled_clips_unless_allowed(tmp_path: Path, server: str) -> None:
    Fake.export = [ann("sintel_000.mp4", 0, [35]), unlabelled("sintel_001.mp4", 1439)]
    r = pull(server, tmp_path)
    assert r.exit_code == 1 and "1/2 clips labelled" in r.output
    assert (
        "download_all_tasks=true" in Fake.calls[-1][1]
    )  # LS exports only labelled tasks otherwise
    assert "sintel_001.mp4" in r.output and not list(tmp_path.iterdir())
    r = pull(server, tmp_path, "--allow-partial", "--labeller", "agent")
    assert r.exit_code == 0, r.output
    doc = json.loads((tmp_path / "sintel_cuts.provisional.json").read_text())
    assert doc["unlabelled_clips"] == ["sintel_001.mp4"] and doc["labeller"] == "agent"
