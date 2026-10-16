"""Shot detection: TorchCodec decode -> 48x27 frames -> TransNetV2 -> half-open shot ranges."""

from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import torch

from nip.ingest.media import load_ffmpeg

_CHUNK = 500  # frames decoded per call


def cuts_from_predictions(probs: np.ndarray, threshold: float = 0.5) -> list[int]:
    """Cut frames from per-frame transition probabilities.

    TransNetV2 flags the last frame of the outgoing shot (a hard cut is a 1-frame run). Each run
    of flagged frames [s, e] becomes one cut at its midpoint, rounded up: a 1-frame run at frame i
    cuts at i + 1, the first frame of the next shot. A cut is the first frame of a new shot.
    """
    above = np.concatenate([[False], probs > threshold, [False]])
    edges = np.flatnonzero(above[1:] != above[:-1])
    runs = zip(edges[::2], edges[1::2], strict=True)  # [s, x) with x = e + 1
    # a run touching either end of the video cannot separate two shots
    return [int(s + x + 1) // 2 for s, x in runs if s > 0 and x < len(probs)]


def shots_from_cuts(cuts: list[int], n_frames: int) -> list[tuple[int, int]]:
    """Contiguous half-open [in, out) ranges covering [0, n_frames)."""
    bounds = [0, *cuts, n_frames]
    return list(zip(bounds[:-1], bounds[1:], strict=True))


@cache
def load_model(device: str = "auto") -> Any:
    from transnetv2_pytorch import TransNetV2  # weights ship inside the wheel

    return TransNetV2(device=device)


def small_frames(video: str | Path) -> torch.Tensor:
    """Every frame of `video` at 27x48 RGB: uint8 [N, 27, 48, 3] (TransNetV2's input)."""
    load_ffmpeg()
    from torchcodec.decoders import VideoDecoder  # type: ignore[attr-defined]
    from torchcodec.transforms import Resize  # type: ignore[attr-defined]

    dec = VideoDecoder(  # threads=0: all cores; the default of 1 decodes 1080p ~4.7x slower
        str(video),
        seek_mode="exact",
        dimension_order="NHWC",
        num_ffmpeg_threads=0,
        transforms=[Resize((27, 48))],
    )
    n = len(dec)
    # ponytail: holds all small frames in RAM (~4 KB/frame, ~0.7 GB for a 2 h film); chunk the
    # model windows if that ever matters.
    chunks = [dec.get_frames_in_range(i, min(i + _CHUNK, n)).data for i in range(0, n, _CHUNK)]
    return torch.cat(chunks)


def detect_shots(
    video: str | Path, *, threshold: float = 0.5, model: Any = None
) -> list[tuple[int, int]]:
    """Shot ranges [in, out) in frames of the decoder's own frame axis."""
    frames = small_frames(video)
    model = model or load_model()
    single, _ = model.predict_frames(frames.to(model.device), quiet=True)
    return shots_from_cuts(cuts_from_predictions(single.numpy(), threshold), len(frames))
