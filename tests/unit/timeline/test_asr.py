import shutil
import subprocess
import wave
from fractions import Fraction

import pytest

from nip.runtime.clients.asr import Segment, StubASR, Word, read_wav
from nip.timeline.asr import extract_audio, to_frames, transcribe_episode

NTSC = Fraction(24000, 1001)


def test_to_frames_uses_the_exact_rate_and_keeps_sub_frame_words_one_frame_long():
    words = (Word("hi", 1000, 1010, 0.9), Word("there", 1500, 2000, 0.8))
    (t,) = to_frames([Segment("hi there", 1000, 2000, words)], NTSC, "en")
    assert t.frames == (24, 48)  # 1000 ms * 24000/1001 / 1000 = 23.98 -> 24
    assert (t.words[0].f_in, t.words[0].f_out) == (24, 25)  # 10 ms is under one frame
    assert t.words[1].f_in == 36 and t.words[1].p == 0.8
    assert t.lang == "en" and t.text == "hi there"


def test_stub_returns_its_canned_segments():
    assert StubASR().transcribe("x.wav") == []
    seg = Segment("a", 0, 100, ())
    assert StubASR(segments=(seg,)).transcribe("x.wav") == [seg]


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe not on PATH")
    out = tmp_path_factory.mktemp("asr") / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", "testsrc2=size=64x64:rate=24000/1001:duration=2",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)],
        check=True,
    )  # fmt: skip
    return out


def test_extract_audio_is_16k_mono_pcm(clip, tmp_path):
    extract_audio(clip, tmp_path / "a.wav")
    pcm = read_wav(tmp_path / "a.wav")
    assert 1.9 < len(pcm) / 16000 < 2.2 and abs(pcm).max() > 0.1  # a 2 s sine, not silence


def test_transcribe_episode_places_stub_segments_on_the_probed_frame_axis(clip):
    stub = StubASR(segments=(Segment("hi", 500, 1500, (Word("hi", 500, 1500, 1.0),)),))
    (t,) = transcribe_episode(clip, stub)
    assert t.frames == (12, 36)  # 500 ms and 1500 ms at 24000/1001


def test_read_wav_rejects_other_formats(tmp_path):
    p = tmp_path / "bad.wav"
    with wave.open(str(p), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(b"\0" * 400)
    with pytest.raises(ValueError, match="16 kHz mono"):
        read_wav(p)


def test_asr_cli_writes_transcript_json_and_merges_into_the_timeline_group(
    clip, tmp_path, monkeypatch
):
    import json

    import typer
    from typer.testing import CliRunner

    from nip.timeline import asr, picture

    stub = StubASR(segments=(Segment("hi", 500, 1500, (Word("hi", 500, 1500, 1.0),)),))
    monkeypatch.setattr(asr, "make_asr", lambda *a, **k: stub)
    root = typer.Typer()
    picture.app.add_typer(
        asr.app
    )  # the wiring line for cli.py (picture.app is mounted at `timeline`)
    root.add_typer(picture.app, name="timeline")
    out = tmp_path / "t.json"
    r = CliRunner().invoke(root, ["timeline", "asr", str(clip), "--out", str(out)])
    picture.app.registered_groups.clear()  # leave the shared app as it was
    assert r.exit_code == 0, r.output
    (seg,) = json.loads(out.read_text())
    assert seg["frames"] == [12, 36] and seg["words"][0]["w"] == "hi"
