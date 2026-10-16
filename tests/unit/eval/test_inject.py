import json
from pathlib import Path

import pysubs2
import pytest

from eval.injectors import REGISTRY, get, register, write_labels
from eval.injectors.base import Injector
from eval.metrics import load_labels

SRT = "1\n00:00:10,000 --> 00:00:12,000\nHello\n\n2\n00:00:20,000 --> 00:00:22,500\nWorld\n"


def run(tmp_path: Path, seed: int) -> tuple[Path, list]:
    src = tmp_path / "sintel_en.srt"
    src.write_text(SRT, encoding="utf-8")
    dst = tmp_path / f"out{seed}" / "sintel_en.srt"
    return dst, get("loc.offset.v1").inject(src, dst, seed)


def test_registered() -> None:
    assert "loc.offset.v1" in REGISTRY


def test_deterministic_and_label_matches_shift(tmp_path: Path) -> None:
    d1, l1 = run(tmp_path, 7)
    d2, l2 = run(tmp_path, 7)
    assert l1 == l2 and d1.read_text() != "" and l1[0].check == "loc.offset"
    frames = int(l1[0].description.split("by ")[1].split(" frames")[0])
    shifted = pysubs2.load(str(d1), encoding="utf-8")[0].start
    assert shifted == 10_000 + round(frames * 1001 / 24)


def test_seeds_vary(tmp_path: Path) -> None:
    descs = {run(tmp_path, s)[1][0].description for s in range(20)}
    assert len(descs) > 1


def test_duplicate_registration_rejected() -> None:
    class Dup(Injector):
        id = "loc.offset.v1"
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
    assert row["injector"] == "loc.offset.v1" and row["target"]["kind"] == "subtitle_file"


def test_offset_labels_are_matchable(tmp_path: Path) -> None:
    _, labels = run(tmp_path, 1)
    out = tmp_path / "labels.jsonl"
    write_labels(labels, out)
    assert load_labels(out) == labels  # the reader validates what the writer wrote
    assert labels[0].target.refs == [f"{tmp_path.name}/sintel/1", f"{tmp_path.name}/sintel/2"]


def test_committed_labels_validate() -> None:
    files = list((Path(__file__).parents[3] / "eval" / "labels").rglob("*.jsonl"))
    assert files
    for f in files:
        assert load_labels(f)
