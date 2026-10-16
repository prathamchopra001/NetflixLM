"""`nip eval inject --set S --seed N` end to end on a tiny corpus (deliverable 2.9A)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from eval.inject import app
from eval.metrics import load_labels
from nip.ingest import parse_bible, parse_fountain, parse_srt

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


def srt(lang: str, n: int = 40) -> str:
    def tc(ms: int) -> str:
        return (
            f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
        )

    out = []
    for i in range(n):
        t = 4_000 * (i + 1)
        text = f"{lang} Scales y Sintel buscan {i} guardianes" if i % 2 else f"{lang} dice hola {i}"
        out.append(f"{i + 1}\n{tc(t)} --> {tc(t + 2400)}\n{text}\n\n")
    return "".join(out)


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """A one-title corpus called `sintel` (its sidecar ships with the repo): a 20 s clip with four
    still stretches, four subtitle tracks, and cached cuts."""
    root = tmp_path_factory.mktemp("corpus")
    d = root / "corpus" / "sintel"
    d.mkdir(parents=True)
    cols = ["0x808080", "0x203060", "0x806020", "0x40a040"]
    ins = [a for c in cols for a in ("-f", "lavfi", "-i", f"color=c={c}:s=320x180:r=24:d=5")]
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex",
         "[0][1][2][3]concat=n=4:v=1:a=0,format=yuv420p", "-c:v", "libx264", str(d / "clip.mkv")],
        check=True,
    )  # fmt: skip
    for lang in ("en", "es", "fr", "de"):
        (d / f"{lang}_sintel_{lang}.srt").write_text(srt(lang), encoding="utf-8")
    shots = root / "shots" / "sintel"
    shots.mkdir(parents=True)
    # cuts every 24 frames + 12 (a cue edge at 4 s * k lands 12 frames from one)
    (shots / "picture.json").write_text(json.dumps({"cuts": list(range(108, 480, 96))}))
    return root / "corpus", root / "shots"


def run(corpus: tuple[Path, Path], out: Path, *extra: str) -> str:
    res = CliRunner().invoke(
        app,
        ["--set", "mvp", "--seed", "3", "--out", str(out), "--corpus", str(corpus[0]),
         "--shots", str(corpus[1]), *extra],
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    return res.output


def files(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
    }


def test_a_set_writes_copies_and_labels_for_every_title(
    corpus: tuple[Path, Path], tmp_path: Path
) -> None:
    out = run(corpus, tmp_path)
    root = tmp_path / "mvp" / "seed3"
    assert "tears-of-steel: no data" in out  # not in the tiny corpus: skipped, not an error
    # real-title tracks (injected or copied) and the re-encoded picture
    names = {p.name for p in (root / "sintel").iterdir()}
    assert {"clip.mkv", "clip.mkv.clr.json", "en_sintel_en.srt", "es_sintel_es.srt"} <= names
    labels = load_labels(root / "labels" / "sintel.jsonl")
    checks = {lb.check for lb in labels}
    assert {"loc.term", "loc.readability", "loc.drift", "loc.offset", "loc.shot_change"} <= checks
    assert any(c.startswith("clr.") for c in checks)
    assert (root / "sintel" / "en_sintel_en.srt").read_bytes() == (
        corpus[0] / "sintel" / "en_sintel_en.srt"
    ).read_bytes()  # the source language is never injected
    # the synthetic show: clean + injected scripts that parse, bible, truth, labels
    for kind in ("clean", "injected"):
        d = root / "synthetic-show" / kind
        assert parse_bible((d / "bible.yaml").read_bytes()).ok
        assert all(parse_fountain(f.read_bytes()).ok for f in sorted(d.glob("*.fountain")))
    plot = load_labels(root / "labels" / "synthetic-show.jsonl")
    assert len(plot) == 12 and all(lb.title == "synthetic-show" for lb in plot)
    # every injected track still parses and has as many cues as its source
    for t in (root / "sintel").glob("*.srt"):
        a = parse_srt(t.read_bytes()).data
        b = parse_srt((corpus[0] / "sintel" / t.name).read_bytes()).data
        assert a and b and len(a.cues) == len(b.cues)


def test_same_seed_is_byte_identical(corpus: tuple[Path, Path], tmp_path: Path) -> None:
    run(corpus, tmp_path / "a")
    run(corpus, tmp_path / "b")
    a, b = files(tmp_path / "a"), files(tmp_path / "b")
    assert a == b and len(a) > 20


def test_only_filter_and_other_seeds(corpus: tuple[Path, Path], tmp_path: Path) -> None:
    run(corpus, tmp_path / "plot", "--only", "plot")
    assert not (tmp_path / "plot" / "mvp" / "seed3" / "sintel").exists()
    assert (tmp_path / "plot" / "mvp" / "seed3" / "synthetic-show" / "injected").exists()
    res = CliRunner().invoke(
        app,
        ["--set", "mvp", "--seed", "4", "--out", str(tmp_path / "s4"), "--corpus", str(corpus[0]),
         "--shots", str(corpus[1]), "--only", "loc,plot"],
    )  # fmt: skip
    assert res.exit_code == 0
    run(corpus, tmp_path / "s3", "--only", "loc,plot")
    s4 = (tmp_path / "s4" / "mvp" / "seed4" / "labels" / "sintel.jsonl").read_bytes()
    assert s4 != (tmp_path / "s3" / "mvp" / "seed3" / "labels" / "sintel.jsonl").read_bytes()


def test_unknown_set_is_a_usage_error(tmp_path: Path) -> None:
    res = CliRunner().invoke(app, ["--set", "nope", "--out", str(tmp_path)])
    assert res.exit_code != 0 and "unknown set" in res.output


REAL = Path(__file__).parents[3] / "data"


@pytest.mark.skipif(
    not (REAL / "corpus" / "sintel" / "es_sintel_es.srt").exists()
    or not (REAL / "exp002" / "runs" / "picture" / "sintel" / "picture.json").exists(),
    reason="needs the Sintel corpus and its cached shots",
)
def test_real_sintel_labels_describe_the_written_tracks(tmp_path: Path) -> None:
    from fractions import Fraction

    from nip.timecode import ms_to_frame

    res = CliRunner().invoke(
        app, ["--set", "smoke", "--seed", "2", "--out", str(tmp_path), "--only", "loc"]
    )
    assert res.exit_code == 0, res.output
    root = tmp_path / "smoke" / "seed2"
    labels = load_labels(root / "labels" / "sintel.jsonl")
    fps = Fraction(24)  # probed from the picture by the injectors; Sintel is 24/1
    cuts = json.loads((REAL / "exp002/runs/picture/sintel/picture.json").read_text())["cuts"]
    tracks = {
        t.name.split("_")[0]: parse_srt(t.read_bytes()).data for t in root.glob("sintel/*.srt")
    }
    for lb in labels:
        assert lb.lang and tracks[lb.lang]
        if lb.target.frames and lb.check in ("loc.term", "loc.shot_change"):
            c = tracks[lb.lang].cues[int(lb.target.refs[0].rsplit("/", 1)[1]) - 1]  # type: ignore[union-attr]
            a = ms_to_frame(c.start_ms, fps)
            assert lb.target.frames == (a, max(ms_to_frame(c.end_ms, fps), a + 1))
            if lb.check == "loc.shot_change":
                assert 1 <= min(abs(e - x) for e in lb.target.frames for x in cuts) <= 11
        if lb.check in ("loc.drift", "loc.offset"):
            assert len(lb.target.refs) == len(tracks[lb.lang].cues)  # type: ignore[union-attr]
