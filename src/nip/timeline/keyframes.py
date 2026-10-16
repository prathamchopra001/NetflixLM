"""Keyframes: middle frame of each shot, plus one every `interval_s` in long shots."""

from fractions import Fraction
from pathlib import Path

from PIL import Image

from nip.ingest.media import load_ffmpeg


def keyframe_frames(
    shot: tuple[int, int], fps: Fraction, long_shot_s: float = 4.0, interval_s: float = 2.0
) -> list[int]:
    """Sorted frame numbers to extract for one shot [in, out).

    Always the middle frame. Shots longer than `long_shot_s` also get frames at in + k * interval
    (k >= 1, inside the shot); a sample within half an interval of the middle frame is dropped.
    """
    a, b = shot
    mid = a + (b - a) // 2
    step = round(fps * Fraction(interval_s).limit_denominator(1000))
    frames = {mid}
    if (b - a) > fps * Fraction(long_shot_s).limit_denominator(1000):
        frames |= {f for f in range(a + step, b, step) if abs(f - mid) > step / 2}
    return sorted(frames)


def extract_keyframes(
    video: str | Path,
    shots: list[tuple[int, int]],
    fps: Fraction,
    out_dir: str | Path,
    *,
    long_shot_s: float = 4.0,
    interval_s: float = 2.0,
    jpeg_quality: int = 90,
) -> list[dict[str, int | str]]:
    """Write `<out_dir>/<shot_index>_<n>.jpg`; return [{"shot", "n", "frame", "file"}] per keyframe.

    The shot index is the position in `shots`; the store step maps it to the shot id when it
    uploads to `{show}/{episode}/keyframes/{shot_id}_{n}.jpg`.
    """
    load_ffmpeg()
    from torchcodec.decoders import VideoDecoder  # type: ignore[attr-defined]

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    wanted = [
        (i, n, f)
        for i, s in enumerate(shots)
        for n, f in enumerate(keyframe_frames(s, fps, long_shot_s, interval_s))
    ]
    dec = VideoDecoder(str(video), seek_mode="exact", dimension_order="NHWC", num_ffmpeg_threads=0)
    records: list[dict[str, int | str]] = []
    for lo in range(0, len(wanted), 64):  # ascending frames, decoded in batches
        batch = wanted[lo : lo + 64]
        imgs = dec.get_frames_at([f for _, _, f in batch]).data.numpy()
        for (i, n, f), img in zip(batch, imgs, strict=True):
            name = f"{i}_{n}.jpg"
            Image.fromarray(img).save(out / name, quality=jpeg_quality)
            records.append({"shot": i, "n": n, "frame": f, "file": name})
    return records
