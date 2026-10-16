"""Media probe (ffprobe) and FFmpeg library discovery (architecture.md > Stage 2 > Media probe).

FFmpeg comes from an LGPL *shared* build (D-027). On Windows TorchCodec finds its DLLs through
`load_ffmpeg()`, which looks in `$NIP_FFMPEG_DIR`, then `<repo>/models/ffmpeg/**/bin`. On Linux the
system / image libraries are used and `load_ffmpeg()` does nothing.
"""

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from nip.timecode import smpte_to_frame

_REPO = Path(__file__).resolve().parents[3]


def ffmpeg_dir() -> Path | None:
    """Directory holding the shared FFmpeg build's DLLs (and ffprobe), or None."""
    env = os.environ.get("NIP_FFMPEG_DIR")
    roots = [Path(env)] if env else [_REPO / "models" / "ffmpeg"]
    for root in roots:
        for dll in sorted(root.glob("**/avcodec-*.dll")):
            return dll.parent
    return None


def load_ffmpeg() -> None:
    """Make the shared FFmpeg DLLs visible to TorchCodec (Windows only; call before decoding)."""
    if sys.platform == "win32" and (d := ffmpeg_dir()):
        os.add_dll_directory(str(d))


def _ffprobe_exe() -> str:
    if (d := ffmpeg_dir()) and (exe := d / "ffprobe.exe").exists():
        return str(exe)
    return shutil.which("ffprobe") or "ffprobe"


@dataclass(frozen=True)
class MediaInfo:
    path: str
    fps: Fraction  # exact, e.g. 24000/1001
    duration_frames: int
    width: int
    height: int
    codec: str
    pix_fmt: str
    start_tc_frames: int  # frame offset of the embedded start timecode (0 if none)
    drop_frame: bool
    audio_streams: int
    vfr: bool  # r_frame_rate != avg_frame_rate: the frame axis is not trustworthy


def _frac(s: str) -> Fraction:
    n, _, d = s.partition("/")
    return Fraction(int(n), int(d or 1))


def parse_probe(path: str, data: dict[str, Any]) -> MediaInfo:
    """Build a MediaInfo from `ffprobe -show_format -show_streams -of json` output."""
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError(f"{path}: no video stream")
    fps = _frac(video.get("avg_frame_rate") or video["r_frame_rate"])
    if fps <= 0:
        raise ValueError(f"{path}: unusable frame rate {video.get('avg_frame_rate')!r}")
    nb = video.get("nb_frames")
    if nb and str(nb).isdigit():
        frames = int(nb)
    else:
        secs = video.get("duration") or data.get("format", {}).get("duration")
        if secs is None:
            raise ValueError(f"{path}: no frame count or duration")
        frames = round(Fraction(str(secs)) * fps)
    tc = next(
        (
            v
            for t in [*streams, data.get("format", {})]
            for k, v in (t.get("tags") or {}).items()
            if k.lower() == "timecode"
        ),
        None,
    )
    return MediaInfo(
        path=path,
        fps=fps,
        duration_frames=frames,
        width=int(video["width"]),
        height=int(video["height"]),
        codec=video.get("codec_name", ""),
        pix_fmt=video.get("pix_fmt", ""),
        start_tc_frames=smpte_to_frame(tc, fps) if tc else 0,
        drop_frame=bool(tc and ";" in tc),
        audio_streams=sum(s.get("codec_type") == "audio" for s in streams),
        vfr=_frac(video["r_frame_rate"]) != fps,
    )


def probe(path: str | Path) -> MediaInfo:
    out = subprocess.run(
        [_ffprobe_exe(), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return parse_probe(str(path), json.loads(out))
