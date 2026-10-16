import math
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image

from nip.timeline.keyframes import extract_keyframes, keyframe_frames

FPS = Fraction(24000, 1001)


def ramp_rgb(n: int) -> float:
    """Decoded gray level of ramp_clip frame n: luma floor(16 + 3.6 * n), limited -> full range."""
    return math.floor(3.6 * n) * 255 / 219  # one frame off changes this by >= 3.6 * 1.164 = 4.2


def test_short_shot_gets_only_middle_frame() -> None:
    assert keyframe_frames((100, 196), FPS) == [148]  # 96 frames = 4.0 s, not longer than 4 s
    assert keyframe_frames((0, 1), FPS) == [0]


def test_long_shot_adds_one_every_two_seconds() -> None:
    # 10 s shot (240 frames): middle 120; samples at 48, 96, 144, 192 (2 s = 48 frames);
    # 96 and 144 are within half an interval (24 frames) of the middle and are dropped
    assert keyframe_frames((0, 240), FPS) == [48, 120, 192]


def test_long_shot_just_over_threshold() -> None:
    # 4.1 s = 99 frames: middle 49; the 48 sample is dropped (too close), 96 stays
    assert keyframe_frames((0, 99), FPS) == [49, 96]


def test_frames_inside_shot_and_sorted() -> None:
    for a, b in [(10, 400), (0, 97), (5, 6), (1000, 1500)]:
        kf = keyframe_frames((a, b), FPS)
        assert kf == sorted(set(kf)) and all(a <= f < b for f in kf)


def test_decoding_is_frame_exact(ramp_clip: Path) -> None:
    """Frame N must carry luma 16 + 3.6 * N (known from the generator, not from the decoder)."""
    from nip.ingest.media import load_ffmpeg

    load_ffmpeg()
    from torchcodec.decoders import VideoDecoder

    dec = VideoDecoder(str(ramp_clip), seek_mode="exact", dimension_order="NHWC")
    assert len(dec) == 60
    order = [59, 31, 3, 30, 0, 45, 29]  # unsorted; crosses key frames at 0 and 30
    got = dec.get_frames_at(order).data.float().mean(dim=(1, 2, 3))
    for n, mean in zip(order, got.tolist(), strict=True):
        assert abs(mean - ramp_rgb(n)) < 1.5, (n, mean)
    seq = dec.get_frames_in_range(0, 60).data.float().mean(dim=(1, 2, 3))
    assert torch.allclose(seq, torch.tensor([ramp_rgb(n) for n in range(60)]), atol=1.5)


def test_keyframes_carry_the_frame_they_claim(ramp_clip: Path, tmp_path: Path) -> None:
    shots = [(0, 10), (10, 31), (31, 40), (40, 60)]
    recs = extract_keyframes(ramp_clip, shots, FPS, tmp_path, long_shot_s=0.2, interval_s=0.2)
    assert len(recs) > len(shots)  # extra keyframes from the interval rule
    for r in recs:
        img = np.asarray(Image.open(tmp_path / str(r["file"])), dtype=float)
        assert abs(img.mean() - ramp_rgb(int(r["frame"]))) < 1.5, r  # JPEG +-1


def test_extract_keyframes(cut_clip: Path, tmp_path: Path, truth: dict[str, Any]) -> None:
    from torchcodec.decoders import VideoDecoder

    cuts = [0, *truth["cuts"], truth["n_frames"]]
    shots = list(zip(cuts[:-1], cuts[1:], strict=True))
    assert [b - a for a, b in shots] == truth["lengths"]
    recs = extract_keyframes(cut_clip, shots, FPS, tmp_path)
    assert [(r["shot"], r["n"]) for r in recs] == [(s, n) for s, n in _expected_ids(shots)]
    dec = VideoDecoder(str(cut_clip), seek_mode="exact", dimension_order="NHWC")
    for r in recs:
        img = np.asarray(Image.open(tmp_path / str(r["file"])), dtype=float)
        ref = dec.get_frame_at(int(r["frame"])).data.numpy().astype(float)
        assert np.abs(img - ref).mean() < 6  # JPEG tolerance


def _expected_ids(shots: list[tuple[int, int]]) -> list[tuple[int, int]]:
    return [(i, n) for i, s in enumerate(shots) for n in range(len(keyframe_frames(s, FPS)))]
