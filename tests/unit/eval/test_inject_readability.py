from fractions import Fraction
from pathlib import Path

import pytest

from eval.injectors import get
from nip.agents.base import run_check
from nip.agents.localization.readability import Readability
from nip.contracts.flag import ProducedBy
from nip.ingest import parse_srt
from nip.ingest.media import MediaInfo
from nip.ingest.script import Element, Scene, Script
from nip.timeline.estimate import build_timeline

TEXT = "Estoy buscando\na alguien."  # 24 chars over 2 s = 12 CPS


def _srt(n: int = 24) -> str:
    """n clean cues: 2 s on screen, 8 s apart."""

    def tc(s: int) -> str:
        return f"00:{s // 60:02d}:{s % 60:02d},000"

    return "".join(f"{i}\n{tc(10 * i)} --> {tc(10 * i + 2)}\n{TEXT}\n\n" for i in range(1, n + 1))


def _flagged(path: Path, fps: Fraction) -> set[str]:
    track = parse_srt(path.read_bytes()).data
    assert track
    media = MediaInfo("x.mkv", fps, 100_000, 1920, 1080, "h264", "yuv420p", 0, False, 1)
    script = Script(None, [Scene("1", "INT. ROOM - DAY", [Element("action", "x")])])
    tl = build_timeline("S01E01", script, media, {"es": track})
    flags = run_check(Readability(["es"]), tl, "r", ProducedBy(model_variant=None, plan_id="p"))
    return {f.evidence[0].ref for f in flags}


@pytest.mark.parametrize("fps", [Fraction(24), Fraction(24000, 1001), Fraction(25)])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_planted_cue_and_nothing_else_is_flagged(
    tmp_path: Path, fps: Fraction, seed: int
) -> None:
    src = tmp_path / "film" / "es_film.srt"
    src.parent.mkdir()
    src.write_text(_srt(), encoding="utf-8")
    assert _flagged(src, fps) == set()
    dst = tmp_path / "out" / src.name
    labels = get("loc.readability.v1").inject(src, dst, seed)
    assert len(labels) == 6
    assert {lb.description.split(": ")[1] for lb in labels} == {
        "chars_per_line",
        "lines",
        "reading_speed",
        "min_duration",
        "max_duration",
        "gap",
    }
    assert all(
        (lb.episode, lb.lang, lb.check) == ("S01E01", "es", "loc.readability") for lb in labels
    )
    assert _flagged(dst, fps) == {r for lb in labels for r in lb.target.refs}


def test_deterministic_per_seed(tmp_path: Path) -> None:
    src = tmp_path / "film" / "es_film.srt"
    src.parent.mkdir()
    src.write_text(_srt(), encoding="utf-8")
    inj = get("loc.readability.v1")
    a = inj.inject(src, tmp_path / "a.srt", 5)
    b = inj.inject(src, tmp_path / "b.srt", 5)
    c = inj.inject(src, tmp_path / "c.srt", 6)
    assert a == b and (tmp_path / "a.srt").read_text() == (tmp_path / "b.srt").read_text()
    assert a != c
