import shutil
import subprocess
from pathlib import Path

import pytest

# Hard cuts at frames 60, 180, 228, 324 of a 424-frame, 24000/1001 clip.
SHOT_LENGTHS = [60, 120, 48, 96, 100]
CUTS = [60, 180, 228, 324]
N_FRAMES = sum(SHOT_LENGTHS)
_SOURCES = ["testsrc2", "rgbtestsrc", "smptebars", "mandelbrot", "testsrc"]


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


@pytest.fixture(scope="session")
def truth() -> dict[str, list[int] | int]:
    return {"cuts": CUTS, "n_frames": N_FRAMES, "lengths": SHOT_LENGTHS}


@pytest.fixture(scope="session")
def media_ok(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Skip tests that need ffmpeg on PATH and TorchCodec with shared FFmpeg libs."""
    tmp_path = tmp_path_factory.mktemp("probe")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe not on PATH")
    try:
        from nip.ingest.media import load_ffmpeg

        load_ffmpeg()  # must run before torchcodec is imported
        from torchcodec.decoders import VideoDecoder

        _ffmpeg(
            "-f", "lavfi", "-i", "testsrc2=size=64x64:rate=24000/1001:duration=1",
            "-pix_fmt", "yuv420p", "-c:v", "libx264", str(tmp_path / "probe.mp4"),
        )  # fmt: skip
        VideoDecoder(str(tmp_path / "probe.mp4"))
    except Exception as e:
        pytest.skip(f"TorchCodec/FFmpeg unavailable: {e}")


@pytest.fixture(scope="session")
def cut_clip(media_ok: None, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """5 visually distinct shots joined by hard cuts, 24000/1001 fps, 320x180, GOP 48."""
    out = tmp_path_factory.mktemp("clips") / "cuts.mp4"
    inputs: list[str] = []
    chains = []
    for i, (src, n) in enumerate(zip(_SOURCES, SHOT_LENGTHS, strict=True)):
        inputs += ["-f", "lavfi", "-i", f"{src}=size=320x180:rate=24000/1001"]
        chains.append(f"[{i}:v]trim=end_frame={n},setpts=PTS-STARTPTS,setsar=1[v{i}]")
    concat = "".join(f"[v{i}]" for i in range(len(SHOT_LENGTHS)))
    graph = ";".join(chains) + f";{concat}concat=n={len(SHOT_LENGTHS)}:v=1[v]"
    _ffmpeg(*inputs, "-filter_complex", graph, "-map", "[v]", "-c:v", "libx264", "-crf", "16",
            "-g", "48", "-pix_fmt", "yuv420p", "-r", "24000/1001", str(out))  # fmt: skip
    return out
