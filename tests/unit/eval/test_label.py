import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from typer.testing import CliRunner

from eval.labeling.labeling import (
    app,
    clip_offset,
    ls_framerate,
    make_clips,
    make_tasks,
    make_verify_clip,
    parse_cuts,
    probe_fps,
    render_config,
    write_cuts,
)

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


def test_framerate_strings() -> None:
    assert ls_framerate((24, 1)) == "24"
    assert ls_framerate((24000, 1001)) == "23.976023976"  # never "24000/1001"
    assert 'framerate="23.976023976"' in render_config((24000, 1001))
    assert "{" not in render_config((24, 1))


def test_offsets_and_tasks() -> None:
    assert [clip_offset(k) for k in (0, 1, 2)] == [0, 1439, 2879]
    tasks = make_tasks("sintel", [Path("sintel_000.mp4"), Path("sintel_001.mp4")])
    assert tasks[1]["data"] == {
        "video": "/data/local-files/?d=labeling/sintel/sintel_001.mp4",
        "offset_frames": 1439,
        "clip": "sintel_001.mp4",
    }


def ann(offset: int, frames: list[int], **kw: object) -> dict:
    result = [
        {"value": {"ranges": [{"start": f, "end": f}], "timelinelabels": ["Cut"]}} for f in frames
    ]
    return {"data": {"offset_frames": offset}, "annotations": [{"result": result, **kw}]}


def test_parse_cuts() -> None:
    tasks = [
        ann(0, [10, 5]),
        ann(1439, [1, 2, 100]),  # frame 1 is the overlap frame -> ignored; 2 -> global 1440
        ann(2879, [1], was_cancelled=True),
        {"data": {"offset_frames": 4319}, "annotations": []},
    ]
    assert parse_cuts(tasks) == [4, 9, 1440, 1538]


def test_parse_cuts_latest_annotation_wins() -> None:
    t = ann(0, [3], updated_at="2026-01-01")
    t["annotations"].append(ann(0, [7], updated_at="2026-02-01")["annotations"][0])
    assert parse_cuts([t]) == [6]


def test_write_cuts(tmp_path: Path) -> None:
    out = tmp_path / "cuts" / "sintel.jsonl"
    write_cuts("sintel", [4, 9], out, "agent")
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert rows[1] == {"title": "sintel", "check": "shot.cut", "frame": 9, "labelled_by": "agent"}


@needs_ffmpeg
def test_verify_clip_ntsc_rate(tmp_path: Path) -> None:
    out = tmp_path / "v.mp4"
    make_verify_clip(out, (24000, 1001), seconds=2)
    assert probe_fps(out) == (24000, 1001)


@needs_ffmpeg
def test_make_clips_frame_counts(tmp_path: Path) -> None:
    src = tmp_path / "film.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=24:duration=5",
            "-c:v",
            "libx264",
            str(src),
        ],
        check=True,
    )
    clips = make_clips(src, tmp_path / "clips", 120, clip_frames=50, width=160)
    counts = [
        int(
            subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-count_frames",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=nb_read_frames",
                    "-of",
                    "csv=p=0",
                    str(c),
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
        for c in clips
    ]
    assert counts == [50, 51, 21]  # clips after the first start one frame early (overlap)


class Fake(BaseHTTPRequestHandler):
    calls: list[tuple[str, str, object, str | None]] = []

    def _do(self) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n)) if n else None
        Fake.calls.append((self.command, self.path, body, self.headers.get("Authorization")))
        out = {"id": 7} if self.path == "/api/projects" else {}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_POST = do_GET = _do

    def log_message(self, *a: object) -> None:
        pass


def test_push_creates_project_storage_and_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "labeling" / "sintel").mkdir(parents=True)
    for k in range(2):
        (tmp_path / "labeling" / "sintel" / f"sintel_{k:03d}.mp4").write_bytes(b"")
    srv = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("LABEL_STUDIO_TOKEN", "abc")
    r = CliRunner().invoke(
        app, ["push", "--url", f"http://127.0.0.1:{srv.server_port}", "--data-dir", str(tmp_path)]
    )
    srv.shutdown()
    assert r.exit_code == 0, r.output
    paths = [(c[0], c[1]) for c in Fake.calls]
    assert paths == [
        ("POST", "/api/projects"),
        ("POST", "/api/storages/localfiles"),
        ("POST", "/api/projects/7/import"),
    ]
    assert Fake.calls[0][2]["label_config"].count('framerate="24"') == 1  # type: ignore[index]
    assert Fake.calls[0][3] == "Token abc" and len(Fake.calls[2][2]) == 2  # type: ignore[arg-type]
    assert os.environ["LABEL_STUDIO_TOKEN"] == "abc"
