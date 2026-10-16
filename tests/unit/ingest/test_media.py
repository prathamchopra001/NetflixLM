import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest

from nip.ingest.media import MediaRejected, parse_probe, probe

VIDEO = {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
         "pix_fmt": "yuv420p", "r_frame_rate": "24000/1001", "avg_frame_rate": "24000/1001",
         "nb_frames": "2400"}  # fmt: skip


def test_parse_basic() -> None:
    m = parse_probe("a.mp4", {"streams": [VIDEO, {"codec_type": "audio"}], "format": {}})
    assert (m.fps, m.duration_frames, m.width, m.height) == (
        Fraction(24000, 1001),
        2400,
        1920,
        1080,
    )
    assert (m.audio_streams, m.start_tc_frames, m.drop_frame) == (1, 0, False)


def test_parse_start_timecode_and_drop_frame() -> None:
    ndf = {**VIDEO, "tags": {"timecode": "01:00:00:00"}}
    assert parse_probe("a", {"streams": [ndf]}).start_tc_frames == 86400  # 3600 s * 24
    df = {**VIDEO, "r_frame_rate": "30000/1001", "avg_frame_rate": "30000/1001",
          "tags": {"TIMECODE": "01:00:00;00"}}  # fmt: skip
    m = parse_probe("a", {"streams": [df]})
    assert m.drop_frame and m.start_tc_frames == 107892  # SMPTE drop-frame hour
    fmt_tc = parse_probe("a", {"streams": [VIDEO], "format": {"tags": {"timecode": "00:00:10:00"}}})
    assert fmt_tc.start_tc_frames == 240


def test_parse_frame_count_from_duration() -> None:
    v = {k: x for k, x in VIDEO.items() if k != "nb_frames"} | {"duration": "100.100000"}
    assert parse_probe("a", {"streams": [v]}).duration_frames == 2400


def test_fps_is_exact_container_rate_even_if_average_rounds_differently() -> None:
    # CFR 24000/1001 whose average was computed as 2997/125 (23.976, off by 1e-6 relative)
    v = {**VIDEO, "avg_frame_rate": "2997/125"}
    assert parse_probe("a", {"streams": [v]}).fps == Fraction(24000, 1001)
    unknown_avg = {**VIDEO, "avg_frame_rate": "0/0"}  # some containers do not report it
    assert parse_probe("a", {"streams": [unknown_avg]}).fps == Fraction(24000, 1001)


def test_rejects_variable_frame_rate() -> None:
    vfr = {**VIDEO, "r_frame_rate": "30/1", "avg_frame_rate": "24000/1001"}
    with pytest.raises(MediaRejected, match="variable frame rate"):
        parse_probe("a", {"streams": [vfr]})
    near = {**VIDEO, "r_frame_rate": "24/1"}  # 24 vs 23.976 is a real mismatch, not rounding
    with pytest.raises(MediaRejected, match="variable frame rate"):
        parse_probe("a", {"streams": [near]})


@pytest.mark.parametrize("rate", ["0/0", "0/1", "", None])
def test_rejects_unknown_frame_rate(rate: str | None) -> None:
    v = {**VIDEO, "r_frame_rate": rate, "avg_frame_rate": rate}
    with pytest.raises(MediaRejected, match="unknown frame rate"):
        parse_probe("a", {"streams": [v]})


def test_cover_art_is_not_the_video_stream() -> None:
    cover = {**VIDEO, "r_frame_rate": "90000/1", "disposition": {"attached_pic": 1}}
    assert parse_probe("a", {"streams": [cover, VIDEO]}).fps == Fraction(24000, 1001)


def test_parse_rejects_audio_only() -> None:
    with pytest.raises(MediaRejected, match="no video stream"):
        parse_probe("a", {"streams": [{"codec_type": "audio"}]})


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="no ffmpeg")
def test_probe_real_file(tmp_path: Path) -> None:
    clip = tmp_path / "c.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "testsrc2=size=160x90:rate=24000/1001:duration=5", "-f", "lavfi", "-i", "sine=duration=5",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-timecode", "01:00:00:00", "-c:a", "aac",
         str(clip)],
        check=True,
    )  # fmt: skip
    m = probe(clip)
    assert m.fps == Fraction(24000, 1001) and m.duration_frames == 120
    assert (m.width, m.height, m.audio_streams, m.start_tc_frames) == (160, 90, 1, 86400)


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="no ffmpeg")
def test_probe_rejects_real_vfr_file(tmp_path: Path) -> None:
    clip = tmp_path / "vfr.mp4"
    subprocess.run(  # drop 2 of every 3 frames, keep original timestamps: gaps in the timeline
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "testsrc2=size=160x90:rate=24000/1001:duration=5", "-vf", "select='not(mod(n,3))'",
         "-fps_mode", "vfr", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)],
        check=True,
    )  # fmt: skip
    with pytest.raises(MediaRejected, match="variable frame rate"):
        probe(clip)


@pytest.mark.skipif(not shutil.which("ffprobe"), reason="no ffprobe")
def test_probe_rejects_corrupt_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"\x00not a video" * 100)
    with pytest.raises(MediaRejected, match="ffprobe cannot read it"):
        probe(bad)


def _ffprobe_prints(monkeypatch: pytest.MonkeyPatch, stdout: str) -> None:
    def run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        assert kw["timeout"]  # a pathological file cannot hang ingest
        return subprocess.CompletedProcess(cmd, 0, stdout, "")

    monkeypatch.setattr(subprocess, "run", run)


@pytest.mark.parametrize(
    ("stdout", "match"),
    [
        ("not json", "unreadable probe data"),
        ('{"streams": [{"codec_type": "video", "r_frame_rate": "24", "nb_frames": "9"}]}', "wid"),
        ('{"streams": [{"codec_type": "video", "r_frame_rate": "x/1"}]}', "unreadable"),
        ('{"streams": [{"codec_type": "audio"}]}', "no video stream"),
    ],
)
def test_probe_maps_bad_output_to_rejection(
    monkeypatch: pytest.MonkeyPatch, stdout: str, match: str
) -> None:
    _ffprobe_prints(monkeypatch, stdout)
    with pytest.raises(MediaRejected, match=match):
        probe("a.mp4")


def test_probe_odd_timecode_tag_is_a_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    v = {**VIDEO, "r_frame_rate": "25/1", "avg_frame_rate": "25/1",
         "tags": {"timecode": "01:00:00;00"}}  # fmt: skip
    _ffprobe_prints(monkeypatch, json.dumps({"streams": [v]}))
    with pytest.raises(MediaRejected, match="unreadable probe data"):
        probe("a.mp4")


def test_probe_timeout_is_a_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    def run(cmd: list[str], **kw: object) -> None:
        raise subprocess.TimeoutExpired(cmd, 60)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(MediaRejected, match="timed out"):
        probe("a.mp4")


def test_missing_ffprobe_is_a_setup_error_not_a_rejection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import nip.ingest.media as media

    monkeypatch.setattr(media, "_ffprobe_exe", lambda: str(tmp_path / "no-ffprobe"))
    with pytest.raises(RuntimeError, match="ffprobe not found") as e:
        probe(tmp_path / "a.mp4")
    assert not isinstance(e.value, MediaRejected)
