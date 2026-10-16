from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image

from nip.timeline.keyframes import extract_keyframes, keyframe_frames

FPS = Fraction(24000, 1001)


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


def test_decoding_is_frame_exact(media_ok: None, tmp_path: Path) -> None:
    from nip.ingest.media import load_ffmpeg

    load_ffmpeg()
    import subprocess

    from torchcodec.decoders import VideoDecoder

    clip = tmp_path / "ramp.mp4"
    subprocess.run(  # luma = frame number + 20 (kept inside limited range)
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "color=gray:size=64x64:rate=24000/1001:duration=5,geq=lum='mod(N,180)+20':cb=128:cr=128",
         "-c:v", "libx264", "-qp", "0", "-g", "30", "-pix_fmt", "yuv420p", str(clip)],
        check=True,
    )  # fmt: skip
    dec = VideoDecoder(str(clip), seek_mode="exact", dimension_order="NHWC")
    order = [100, 3, 77, 119, 0, 45]  # random access, incl. frames far from a key frame
    got = dec.get_frames_at(order).data.float().mean(dim=(1, 2, 3))
    want = dec.get_frames_at(sorted(order)).data.float().mean(dim=(1, 2, 3))
    assert torch.equal(got[np.argsort(order)], want)
    # luma rises with the frame number, so the i-th frame returned is frame i
    assert torch.all(want[1:] > want[:-1])


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
