"""Speech-to-text client (`asr` slot): faster-whisper in-process, a stub, and the Serve actor.

Times are integer milliseconds from the start of the audio; frame placement belongs to
`nip.timeline.asr`. Variant ids are the catalog's (`faster-whisper-large-v3[-turbo]-int8`); the
`-int8` suffix is the CTranslate2 compute type; the fp16 CT2 repos are converted on load.
"""

import os
import sys
import wave
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

# The turbo variant has no `base_model` in the catalog (B-037): this is the CT2 repo it resolves to
# (the one faster-whisper's own "turbo" alias points at).
FALLBACK_REPOS = {
    "faster-whisper-large-v3-int8": "Systran/faster-whisper-large-v3",
    "faster-whisper-large-v3-turbo-int8": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}


@dataclass(frozen=True)
class Word:
    w: str
    start_ms: int
    end_ms: int
    p: float


@dataclass(frozen=True)
class Segment:
    text: str
    start_ms: int
    end_ms: int
    words: tuple[Word, ...]


def _ms(seconds: float) -> int:
    return round(seconds * 1000)


def read_wav(path: str | Path) -> np.ndarray[Any, np.dtype[np.float32]]:
    """16 kHz mono PCM16 wav -> float32 in [-1, 1]. Decoding here keeps PyAV out of the path:
    faster-whisper 1.2.1's own decoder breaks on PyAV 19 (`metadata_errors` kwarg)."""
    with wave.open(str(path), "rb") as f:
        if (f.getframerate(), f.getnchannels(), f.getsampwidth()) != (16000, 1, 2):
            raise ValueError(f"{path}: need 16 kHz mono 16-bit PCM wav (nip.timeline.asr makes it)")
        pcm = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16)
    return pcm.astype(np.float32) / 32768.0


@cache
def add_cuda_dll_dirs() -> None:
    """Windows: CTranslate2 4.x loads CUDA 12 cuBLAS / cuDNN 9 by name. The `nvidia-*-cu12` pip
    wheels (a `chore(deps)` extra if the host lacks them) ship them under site-packages/nvidia."""
    if sys.platform != "win32":
        return
    for p in sys.path:
        for d in Path(p).glob("nvidia/*/bin"):
            os.add_dll_directory(str(d))
            os.environ["PATH"] = f"{d}{os.pathsep}{os.environ['PATH']}"


class FasterWhisperASR:
    def __init__(
        self,
        variant: str,
        repo: str | None = None,
        device: str = "cuda",
        vad: bool = False,
        min_prob: float = 0.5,
        **opts: Any,
    ) -> None:
        add_cuda_dll_dirs()
        from faster_whisper import WhisperModel  # CTranslate2: imported only when a model loads

        self.variant, self.vad, self.min_prob, self.opts = variant, vad, min_prob, opts
        self.model = WhisperModel(
            repo or FALLBACK_REPOS[variant],
            device=device,
            compute_type="int8" if variant.endswith("int8") else "default",
        )

    def transcribe(self, audio: str | Path, lang: str | None = "en") -> list[Segment]:
        """Segments with word timestamps. `condition_on_previous_text=False` stops one bad segment
        poisoning the rest. `vad` is off by default: faster-whisper 1.2.1's VAD pass dropped short
        exclamations and mis-timed whole segments on Sintel (EXP-003 notes). Whisper then
        hallucinates over music with low word confidence, so segments whose mean word probability
        is under `min_prob` are dropped."""
        kw: dict[str, Any] = {
            "language": lang,
            "word_timestamps": True,
            "vad_filter": self.vad,
            "condition_on_previous_text": False,
            "temperature": 0.0,
        } | self.opts  # `opts` override: e.g. faster-whisper's temperature fallback tuple
        segs, _ = self.model.transcribe(read_wav(audio), **kw)
        out = [
            Segment(
                s.text.strip(),
                _ms(s.start),
                _ms(s.end),
                tuple(Word(w.word.strip(), _ms(w.start), _ms(w.end), float(w.probability))
                      for w in (s.words or [])),
            )
            for s in segs
        ]  # fmt: skip
        return [
            s
            for s in out
            if not s.words or sum(w.p for w in s.words) / len(s.words) >= self.min_prob
        ]


class StubASR:
    """cpu-profile backend: returns the canned segments it was given (none by default)."""

    def __init__(self, variant: str = "stub", segments: tuple[Segment, ...] = ()) -> None:
        self.variant, self.segments = variant, segments

    def transcribe(self, audio: str | Path, lang: str | None = "en") -> list[Segment]:
        return list(self.segments)


ASR = FasterWhisperASR | StubASR


def make_asr(variant: str, catalog: Any = None, device: str = "cuda", **opts: Any) -> ASR:
    """Backend for a catalog variant: the stub when its engine is `stub`, else faster-whisper."""
    v = next((v for v in catalog.variants if v.id == variant), None) if catalog else None
    if v is not None and v.engine == "stub":
        return StubASR(variant)
    return FasterWhisperASR(variant, v.repo if v else None, device, **opts)


class Actor:
    """Serve deployment (docs: Serve actors, serving._bind): `POST {"audio_path", "lang"}` ->
    `{"segments": [...]}`. The path is on storage shared with the replica."""

    def __init__(self, variant: str) -> None:
        from nip.timeline.asr import asr_kwargs
        from nip.timeline.picture import timeline_config  # the pipeline's own settings

        self.asr = FasterWhisperASR(variant, **asr_kwargs(timeline_config()["asr"]))

    async def __call__(self, request: Any) -> dict[str, Any]:
        body = await request.json()
        segs = self.asr.transcribe(body["audio_path"], body.get("lang", "en"))
        return {"variant": self.asr.variant, "segments": [_seg_json(s) for s in segs]}


def _seg_json(s: Segment) -> dict[str, Any]:
    return {
        "text": s.text,
        "start_ms": s.start_ms,
        "end_ms": s.end_ms,
        "words": [
            {"w": w.w, "start_ms": w.start_ms, "end_ms": w.end_ms, "p": w.p} for w in s.words
        ],
    }
