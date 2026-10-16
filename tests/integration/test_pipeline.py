"""Walking skeleton on a synthetic clip: probe -> TransNetV2 shots -> keyframes -> timeline ->
loc.readability -> verification -> report (deliverable 1.10)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from nip.pipeline import run_pipeline

# No marker: TransNetV2 runs on the CPU for this 6 s clip, so the cpu profile (CI) runs the whole
# walking skeleton (ffmpeg is required; under NIP_CI=1 a missing ffmpeg fails, not skips).

SCRIPT = "INT. ROOM - DAY #1#\n\nMaya enters.\n"
EN = "1\n00:00:00,500 --> 00:00:02,500\nHello.\n\n2\n00:00:03,000 --> 00:00:05,000\nBye.\n"
ES = (  # cue 2: 45 characters on one line (15.5 CPS)
    "1\n00:00:00,500 --> 00:00:02,500\nHola.\n\n"
    "2\n00:00:03,000 --> 00:00:05,900\nEsta línea tiene más de cuarenta y dos letras\n"
)


@pytest.fixture
def clip(tmp_path: Path) -> Path:
    """Two 3 s shots (testsrc2 | smptebars) joined by a hard cut at frame 72, 24 fps."""
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not on PATH")
    out = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=3",
         "-f", "lavfi", "-i", "smptebars=size=320x180:rate=24:duration=3",
         "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
        check=True,
    )  # fmt: skip
    return out


def test_pipeline_on_synthetic_clip(clip: Path, tmp_path: Path) -> None:
    files = {"s.fountain": SCRIPT, "en.srt": EN, "es.srt": ES}
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    out = tmp_path / "out"
    summary = run_pipeline(
        episode="E1",
        script=tmp_path / "s.fountain",
        subs={"en": tmp_path / "en.srt", "es": tmp_path / "es.srt"},
        source_lang="en",
        out_dir=out,
        video=clip,
    )
    assert summary["spans"]["shot"] == 2 and summary["spans"]["keyframe"] >= 2
    tl = json.loads((out / "timeline.json").read_text())
    assert tl["fps"] == [24, 1] and tl["duration_frames"] == 144
    shots = [s["frames"] for s in tl["spans"] if s["kind"] == "shot"]
    assert abs(shots[1][0] - 72) <= 2
    report = json.loads((out / "report.json").read_text())
    loc = next(s for s in report["sections"] if s["category"] == "localization")
    assert [f["title"] for f in loc["flags"]] == ["Cue 2: 45 characters/line (max 42)"]
    flag = json.loads((out / "flags.jsonl").read_text())
    assert flag["verification"] == {
        "evidence": "pass",
        "rule_recheck": "pass",
        "judge": "n/a",
        "judge_variant": None,
    }
    assert (out / "picture" / "keyframes" / "0_0.jpg").exists()
