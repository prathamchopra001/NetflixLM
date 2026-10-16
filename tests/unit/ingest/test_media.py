import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest

from nip.ingest.media import parse_probe, probe

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
    assert (m.audio_streams, m.start_tc_frames, m.drop_frame, m.vfr) == (1, 0, False, False)


def test_parse_start_timecode_and_drop_frame() -> None:
    ndf = {**VIDEO, "tags": {"timecode": "01:00:00:00"}}
    assert parse_probe("a", {"streams": [ndf]}).start_tc_frames == 86400  # 3600 s * 24
    df = {**VIDEO, "r_frame_rate": "30000/1001", "avg_frame_rate": "30000/1001",
          "tags": {"TIMECODE": "01:00:00;00"}}  # fmt: skip
    m = parse_probe("a", {"streams": [df]})
    assert m.drop_frame and m.start_tc_frames == 107892  # SMPTE drop-frame hour
    fmt_tc = parse_probe("a", {"streams": [VIDEO], "format": {"tags": {"timecode": "00:00:10:00"}}})
    assert fmt_tc.start_tc_frames == 240


def test_parse_frame_count_from_duration_and_vfr() -> None:
    v = {k: x for k, x in VIDEO.items() if k != "nb_frames"} | {"duration": "100.100000"}
    assert parse_probe("a", {"streams": [v]}).duration_frames == 2400
    vfr = {**VIDEO, "r_frame_rate": "30/1"}
    assert parse_probe("a", {"streams": [vfr]}).vfr


def test_parse_rejects_audio_only() -> None:
    with pytest.raises(ValueError, match="no video stream"):
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
    assert json.dumps(m.fps.numerator) == "24000"
