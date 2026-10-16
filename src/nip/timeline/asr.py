"""Transcription stage of the timeline: audio extract -> speech-to-text -> frame-placed segments.

`transcript_segment` rows (data-model.md): a frame range, text, per-word `{w, f_in, f_out, p}`.
Frame = `ms_to_frame(ms, fps)` with the picture's exact rate; audio and picture both start at 0 of
the container, so no offset is applied (start_tc_frames is display-only).
"""

import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Annotated, Any

import typer

from nip.ingest.media import MediaRejected, ffmpeg_dir, probe
from nip.runtime.clients.asr import ASR, Segment, make_asr
from nip.timecode import ms_to_frame
from nip.timeline.picture import timeline_config

app = typer.Typer(no_args_is_help=True)


@dataclass(frozen=True)
class TranscriptWord:
    w: str
    f_in: int
    f_out: int
    p: float


@dataclass(frozen=True)
class TranscriptSegment:
    frames: tuple[int, int]  # [in, out)
    lang: str
    text: str
    words: tuple[TranscriptWord, ...]

    def to_row(self, episode_id: int) -> dict[str, Any]:
        """Values for an insert into `transcript_segment` (frames as an int8range literal)."""
        from sqlalchemy.dialects.postgresql import Range

        return {
            "episode_id": episode_id,
            "frames": Range(self.frames[0], self.frames[1], bounds="[)"),
            "lang": self.lang,
            "text": self.text,
            "words": [asdict(w) for w in self.words],
        }


def _span(start_ms: int, end_ms: int, fps: Fraction) -> tuple[int, int]:
    a = ms_to_frame(start_ms, fps)
    return a, max(ms_to_frame(end_ms, fps), a + 1)  # a sub-frame word keeps one frame


def to_frames(segments: list[Segment], fps: Fraction, lang: str) -> list[TranscriptSegment]:
    return [
        TranscriptSegment(
            _span(s.start_ms, s.end_ms, fps),
            lang,
            s.text,
            tuple(TranscriptWord(w.w, *_span(w.start_ms, w.end_ms, fps), w.p) for w in s.words),
        )
        for s in segments
    ]


def extract_audio(video: Path, wav: Path, stream: int = 0) -> None:
    """16 kHz mono PCM16 wav of audio stream `stream` (Whisper's input format)."""
    d = ffmpeg_dir()
    exe = str(d / "ffmpeg.exe") if d and (d / "ffmpeg.exe").exists() else shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg not found: install FFmpeg (D-027)")
    r = subprocess.run(
        [exe, "-y", "-v", "error", "-i", str(video), "-map", f"0:a:{stream}", "-vn", "-ac", "1",
         "-ar", "16000", "-c:a", "pcm_s16le", str(wav)],
        capture_output=True, text=True,
    )  # fmt: skip
    if r.returncode:
        raise MediaRejected(f"{video}: cannot extract audio stream {stream}: {r.stderr.strip()}")


def transcribe_episode(
    video: Path, backend: ASR, lang: str = "en", wav: Path | None = None
) -> list[TranscriptSegment]:
    """Frame-placed transcript of `video`'s first audio stream (`wav` keeps the extracted audio)."""
    info = probe(video)
    if info.audio_streams == 0:
        raise MediaRejected(f"{video}: no audio stream")
    with tempfile.TemporaryDirectory() as tmp:
        wav = wav or Path(tmp) / "audio.wav"
        extract_audio(video, wav)
        segs = backend.transcribe(wav, lang)
    return to_frames(segs, info.fps, lang)


@app.command("asr")
def asr_command(
    video: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    out: Annotated[Path, typer.Option(help="transcript.json to write")],
    variant: Annotated[str | None, typer.Option(help="catalog asr variant")] = None,
    lang: Annotated[str | None, typer.Option(help="audio language")] = None,
) -> None:
    """Transcribe a picture file's audio into frame-placed segments."""
    cfg = timeline_config()["asr"]
    variant, lang = variant or cfg["variant"], lang or cfg["lang"]
    try:
        segs = transcribe_episode(
            video, make_asr(variant, vad=cfg["vad"], min_prob=cfg["min_prob"]), lang
        )
    except MediaRejected as e:
        typer.echo(f"INPUT_REJECTED: {e}", err=True)
        raise typer.Exit(1) from e
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([asdict(s) for s in segs]), encoding="utf-8")
    typer.echo(f"{len(segs)} segments, {sum(len(s.words) for s in segs)} words -> {out}")
