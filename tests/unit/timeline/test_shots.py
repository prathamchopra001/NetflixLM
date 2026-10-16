from pathlib import Path
from typing import Any

import numpy as np
import pytest
import torch

from nip.timeline.shots import cuts_from_predictions, detect_shots, shots_from_cuts, small_frames


def test_cuts_from_predictions() -> None:
    p = np.zeros(20)
    p[[4, 10, 11, 12, 13]] = 0.9  # hard cut after frame 4; 4-frame dissolve at 10..13
    cuts = cuts_from_predictions(p)
    assert cuts == [5, 12] and all(type(c) is int for c in cuts)
    assert cuts_from_predictions(np.zeros(5)) == []
    assert cuts_from_predictions(np.ones(5)) == []  # all-transition: no usable cut inside
    q = np.zeros(10)
    q[[0, 9]] = 1  # flags at the very ends cannot split the video
    assert cuts_from_predictions(q) == []


def test_shots_cover_axis_without_gaps() -> None:
    assert shots_from_cuts([5, 12], 20) == [(0, 5), (5, 12), (12, 20)]
    assert shots_from_cuts([], 7) == [(0, 7)]


class _FrameDiffModel:
    """Stand-in for TransNetV2: flags frame i when frame i+1 looks very different from it."""

    device = torch.device("cpu")

    def predict_frames(self, frames: torch.Tensor, quiet: bool = False) -> tuple[torch.Tensor, ...]:
        f = frames.float()
        diff = (f[1:] - f[:-1]).abs().mean(dim=(1, 2, 3))
        p = torch.cat([(diff > 30).float(), torch.zeros(1)])
        return p, p


def test_small_frames_shape(cut_clip: Path, truth: dict[str, Any]) -> None:
    f = small_frames(cut_clip)
    assert f.shape == (truth["n_frames"], 27, 48, 3) and f.dtype == torch.uint8


def test_detect_shots_pipeline_with_stub_model(cut_clip: Path, truth: dict[str, Any]) -> None:
    shots = detect_shots(cut_clip, model=_FrameDiffModel())
    assert [s[0] for s in shots[1:]] == truth["cuts"]
    assert shots[0][0] == 0 and shots[-1][1] == truth["n_frames"]


@pytest.mark.gpu
def test_transnetv2_finds_hard_cuts(cut_clip: Path, truth: dict[str, Any]) -> None:
    cuts = truth["cuts"]
    from nip.timeline.shots import load_model

    shots = detect_shots(cut_clip, model=load_model("cuda"))
    found = [s[0] for s in shots[1:]]
    assert len(found) == len(cuts)
    assert all(abs(f - c) <= 2 for f, c in zip(found, cuts, strict=True)), (found, cuts)


def test_picture_cli_writes_json(
    cut_clip: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from typer.testing import CliRunner

    from nip.timeline import picture, shots

    real = shots.detect_shots
    monkeypatch.setattr(shots, "detect_shots", lambda v, **k: real(v, model=_FrameDiffModel()))
    res = CliRunner().invoke(picture.app, ["picture", str(cut_clip), "--out-dir", str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = json.loads((tmp_path / "picture.json").read_text())
    assert out["fps"] == [24000, 1001] and out["duration_frames"] == 424
    assert len(out["shots"]) == 5 and (tmp_path / "keyframes" / "0_0.jpg").exists()


def test_picture_cli_rejects_vfr(tmp_path: Path, media_ok: None) -> None:
    import subprocess

    from typer.testing import CliRunner

    from nip.timeline import picture

    clip = tmp_path / "vfr.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "testsrc2=size=160x90:rate=24000/1001:duration=5", "-vf", "select='not(mod(n,3))'",
         "-fps_mode", "vfr", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)],
        check=True,
    )  # fmt: skip
    res = CliRunner().invoke(picture.app, ["picture", str(clip), "--out-dir", str(tmp_path / "o")])
    assert res.exit_code == 1 and "INPUT_REJECTED" in res.output
