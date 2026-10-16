import json
from fractions import Fraction
from pathlib import Path

import pytest

from eval.injectors import REGISTRY, get, register, write_labels
from eval.injectors.base import Injector
from eval.metrics import load_labels
from nip.ingest import parse_srt
from nip.timecode import frame_to_ms

SRT = "1\n00:00:10,000 --> 00:00:12,000\nHello\n\n2\n00:00:20,000 --> 00:00:22,500\nWorld\n"
CRLF = (
    b"7\r\n00:00:10,000 --> 00:00:12,000\r\nHello\r\n\r\n"
    b"9\r\n00:00:20,000 --> 00:00:22,500\r\nWorld\r\n"
)


def run(tmp_path: Path, seed: int, fps: Fraction = Fraction(24)) -> tuple[Path, list]:
    src = tmp_path / "film" / "es_film.srt"
    src.parent.mkdir(exist_ok=True)
    src.write_text(SRT, encoding="utf-8")
    dst = tmp_path / f"out{seed}" / "es_film.srt"
    return dst, get("loc.offset.v2").inject(src, dst, seed, fps=fps)


def test_registered() -> None:
    assert "loc.offset.v2" in REGISTRY


@pytest.mark.parametrize("fps", [Fraction(24), Fraction(24000, 1001)])
def test_deterministic_and_label_matches_shift(tmp_path: Path, fps: Fraction) -> None:
    d1, l1 = run(tmp_path, 7, fps)
    d2, l2 = run(tmp_path, 7, fps)
    assert l1 == l2 and d1.read_text() != "" and l1[0].check == "loc.offset"
    frames = int(l1[0].description.split("by ")[1].split(" frames")[0])
    shifted = parse_srt(d1.read_bytes()).data.cues[0].start_ms  # type: ignore[union-attr]
    # the shift is the probed rate's frames, not a hard-coded 23.976
    assert shifted == 10_000 + (1 if frames > 0 else -1) * frame_to_ms(abs(frames), fps)
    assert f"at {fps} fps" in l1[0].description


def test_file_numbering_and_endings_survive(tmp_path: Path) -> None:
    src = tmp_path / "film" / "es_film.srt"
    src.parent.mkdir()
    src.write_bytes(CRLF)
    dst = tmp_path / "o.srt"
    labels = get("loc.offset.v2").inject(src, dst, 1, fps=Fraction(24))
    out = dst.read_bytes().decode()
    assert out.startswith("7\r\n") and "\r\n\r\n9\r\n" in out and out.endswith("World\r\n")
    # labels use the timeline's cue numbering (position), not the file's own numbers
    assert labels[0].target.refs == ["film/es/1", "film/es/2"]


def test_seeds_vary(tmp_path: Path) -> None:
    descs = {run(tmp_path, s)[1][0].description for s in range(20)}
    assert len(descs) > 1


def test_duplicate_registration_rejected() -> None:
    class Dup(Injector):
        id = "loc.offset.v2"
        check = "x"

        def inject(self, src: Path, dst: Path, seed: int) -> list:
            return []

    with pytest.raises(ValueError):
        register(Dup)


def test_write_labels_jsonl(tmp_path: Path) -> None:
    _, labels = run(tmp_path, 1)
    out = tmp_path / "labels" / "smoke" / "sintel.jsonl"
    write_labels(labels, out)
    row = json.loads(out.read_text().splitlines()[0])
    assert row["injector"] == "loc.offset.v2" and row["target"]["kind"] == "subtitle_track"


def test_offset_labels_are_matchable(tmp_path: Path) -> None:
    _, labels = run(tmp_path, 1)
    out = tmp_path / "labels.jsonl"
    write_labels(labels, out)
    assert load_labels(out) == labels  # the reader validates what the writer wrote
    assert labels[0].target.refs == ["film/es/1", "film/es/2"]
    assert (labels[0].episode, labels[0].lang, labels[0].title) == ("film", "es", "film")


def test_committed_labels_validate() -> None:
    files = list((Path(__file__).parents[3] / "eval" / "labels").rglob("*.jsonl"))
    assert files
    for f in files:
        assert load_labels(f)
