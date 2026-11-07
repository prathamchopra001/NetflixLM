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


class MediaRejected(ValueError):
    """Picture file refused at the door (architecture.md > Validation at the door)."""


_VFR_TOLERANCE = Fraction(5, 10000)  # 0.05%: below the 0.1% gap between 24 and 24000/1001


def _frac(s: str | None) -> Fraction:
    """ffprobe rate such as '24000/1001'; unknown ('0/0', missing) -> 0."""
    n, _, d = (s or "0").partition("/")
    return Fraction(int(n), int(d or 1)) if int(d or 1) else Fraction(0)


def parse_probe(path: str, data: dict[str, Any]) -> MediaInfo:
    """Build a MediaInfo from `ffprobe -show_format -show_streams -of json` output."""
    streams = data.get("streams", [])
    video = next(
        (
            s
            for s in streams
            if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
        ),
        None,
    )
    if video is None:
        raise MediaRejected(f"{path}: no video stream")
    # r_frame_rate is the exact container rate of a constant-rate file; avg_frame_rate is
    # frames / duration and is only used to detect variable frame rate.
    fps, avg = _frac(video.get("r_frame_rate")), _frac(video.get("avg_frame_rate"))
    if fps <= 0:
        raise MediaRejected(f"{path}: unknown frame rate {video.get('r_frame_rate')!r}")
    if avg > 0 and abs(avg - fps) > fps * _VFR_TOLERANCE:
        raise MediaRejected(f"{path}: variable frame rate (r={fps}, average={avg})")
    nb = video.get("nb_frames")
    if nb and str(nb).isdigit():
        frames = int(nb)
    else:
        secs = video.get("duration") or data.get("format", {}).get("duration")
        if secs is None:
            raise MediaRejected(f"{path}: no frame count or duration")
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
    )


PROBE_TIMEOUT_S = 60  # ffprobe reads headers only; a file that takes longer is refused


def probe(path: str | Path) -> MediaInfo:
    """MediaInfo of `path`. MediaRejected for any file ffprobe or `parse_probe` cannot read;
    RuntimeError when ffprobe itself is missing (a broken install, not a bad input)."""
    exe = _ffprobe_exe()
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=PROBE_TIMEOUT_S,
        ).stdout
        return parse_probe(str(path), json.loads(out))
    except FileNotFoundError as e:
        raise RuntimeError(f"ffprobe not found ({exe}): install FFmpeg (D-027)") from e
    except subprocess.CalledProcessError as e:
        raise MediaRejected(f"{path}: ffprobe cannot read it: {(e.stderr or '').strip()}") from e
    except subprocess.TimeoutExpired as e:
        raise MediaRejected(f"{path}: ffprobe timed out after {PROBE_TIMEOUT_S} s") from e
    except MediaRejected:
        raise
    except (ValueError, KeyError, TypeError) as e:  # bad JSON, missing field, odd timecode tag
        raise MediaRejected(f"{path}: unreadable probe data: {e!r}") from e
