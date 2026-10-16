"""faster-whisper on real film audio (needs the GPU, the CT2 weights and the Sintel corpus file).

Run under data/gpu.lock. 23 s of Sintel (112-135 s) hold the official cues "You're a fool..." (SRT
118.0 s) and "Thank you." (125.25 s); Whisper's word times land within 1 s of those.
"""

import subprocess
from fractions import Fraction
from pathlib import Path

import pytest

from nip.runtime.clients.asr import FasterWhisperASR
from nip.timeline.asr import to_frames

pytestmark = pytest.mark.gpu

SINTEL = Path(__file__).resolve().parents[2] / "data/corpus/sintel/Sintel.2010.1080p.mkv"


def test_turbo_places_dialogue_within_a_second_of_the_official_cues(tmp_path: Path) -> None:
    if not SINTEL.exists():
        pytest.skip("Sintel not fetched (nip eval corpus fetch)")
    wav = tmp_path / "a.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", "112", "-t", "23", "-i", str(SINTEL),
         "-vn", "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)],
        check=True,
    )  # fmt: skip
    asr = FasterWhisperASR("faster-whisper-large-v3-turbo-int8")
    (fool,) = [s for s in asr.transcribe(wav) if "fool" in s.text]
    (seg,) = to_frames([fool], Fraction(24), "en")
    assert abs(seg.frames[0] - (118.0 - 112) * 24) <= 24
