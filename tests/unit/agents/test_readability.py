from pathlib import Path

import pytest

from nip.agents.base import run_check
from nip.agents.localization.readability import Readability, rule_pack
from nip.contracts.flag import EvidenceKind, EvidenceRole, ProducedBy, Tier
from nip.contracts.timeline import Span, Timeline

PB = ProducedBy(model_variant=None, plan_id="plan_1")
OK_TEXT = "Hola."  # 5 chars: fine at any duration >= 20 frames


def _tl(cues: list[tuple[int, int, str]], lang: str = "es", fps: int = 24) -> Timeline:
    spans = [
        Span(kind=EvidenceKind.SUBTITLE_CUE, ref=f"E1/{lang}/{i}", frames=(a, b), lang=lang, text=t)
        for i, (a, b, t) in enumerate(cues, 1)
    ]
    return Timeline(episode="E1", fps=(fps, 1), duration_frames=100_000, spans=spans)


def _titles(tl: Timeline, lang: str = "es") -> list[str]:
    return [f.title for f in run_check(Readability([lang]), tl, "run_1", PB)]


def test_rule_pack_tag_fallback() -> None:
    assert rule_pack("es")["readability"]["reading_speed_cps"] == {"adult": 17, "children": 13}
    assert rule_pack("es-419")["readability"] == rule_pack("es")["readability"]
    assert rule_pack("en")["readability"]["reading_speed_cps"]["adult"] == 20
    assert rule_pack("fr-FR")["readability"]["max_chars_per_line"] == 42  # from _base


def test_language_without_pack_is_rejected() -> None:
    with pytest.raises(ValueError, match="no readability rule pack"):
        Readability(["xx"])


def test_more_specific_pack_overrides_keys(tmp_path: Path) -> None:
    (tmp_path / "_base.yaml").write_text("readability: {max_lines: 2, max_chars_per_line: 42}")
    (tmp_path / "es-ES.yaml").write_text("readability: {max_lines: 3}")
    assert rule_pack("es-ES", tmp_path)["readability"] == {"max_lines": 3, "max_chars_per_line": 42}


def test_clean_cue_passes() -> None:
    assert _titles(_tl([(0, 48, OK_TEXT), (50, 98, "Adiós.")])) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("uno\ndos\ntres", "3 lines (max 2)"),
        ("a" * 43, "43 characters/line (max 42)"),
        ("a" * 42, None),
        ("a\nb", None),
    ],
)
def test_lines_and_line_length(text: str, expected: str | None) -> None:
    titles = _titles(_tl([(0, 96, text)]))  # 4 s: CPS stays under 17
    assert titles == ([f"Cue 1: {expected}"] if expected else [])


def test_reading_speed_counts_spaces_not_line_breaks() -> None:
    # 1 s cues. 17 visible characters + a line break: 17 CPS, allowed (18 if the break counted).
    text = "abcdefgh\nij lmnopq"
    assert len(text.replace("\n", "")) == 17
    assert _titles(_tl([(0, 24, text)])) == []
    # 18 characters including a space: 18 CPS, flagged (17 if the space did not count).
    text = "abcdefgh ij lmnopq"
    assert len(text) == 18
    assert _titles(_tl([(0, 24, text)])) == ["Cue 1: reading speed 18.0 CPS (max 17)"]


def test_reading_speed_uses_language_pack() -> None:
    text = "a" * 19  # 19 CPS over 1 s: over es (17), under en (20)
    assert _titles(_tl([(0, 24, text)], lang="es")) == ["Cue 1: reading speed 19.0 CPS (max 17)"]
    assert _titles(_tl([(0, 24, text)], lang="en"), lang="en") == []


@pytest.mark.parametrize(
    ("frames", "expected"),
    [
        (19, "duration 0.79 s (min 5/6 s)"),
        (20, None),  # 5/6 s at 24 fps
        (168, None),  # 7 s
        (169, "duration 7.04 s (max 7 s)"),
    ],
)
def test_min_and_max_duration(frames: int, expected: str | None) -> None:
    titles = _titles(_tl([(0, frames, OK_TEXT)]))
    assert titles == ([f"Cue 1: {expected}"] if expected else [])


def test_min_duration_follows_the_frame_rate() -> None:
    # 5/6 s = 20.83 frames at 25 fps: 20 frames is too short there, 21 is fine
    assert _titles(_tl([(0, 20, OK_TEXT)], fps=25)) == ["Cue 1: duration 0.80 s (min 5/6 s)"]
    assert _titles(_tl([(0, 21, OK_TEXT)], fps=25)) == []


@pytest.mark.parametrize(
    ("gap", "expected"),
    [
        (-3, "overlaps the previous cue by 3 frames"),
        (0, "gap of 0 frames (min 2)"),
        (1, "gap of 1 frames (min 2)"),
        (2, None),
        (3, "gap of 3 frames should be closed to 2"),
        (11, "gap of 11 frames should be closed to 2"),
        (12, None),  # half a second at 24 fps
    ],
)
def test_gaps(gap: int, expected: str | None) -> None:
    tl = _tl([(0, 48, OK_TEXT), (48 + gap, 96 + gap, OK_TEXT)])
    flags = run_check(Readability(["es"]), tl, "run_1", PB)
    assert [f.title for f in flags] == ([f"Cue 2: {expected}"] if expected else [])
    if expected:
        f = flags[0]
        assert [(e.ref, e.role) for e in f.evidence] == [
            ("E1/es/2", EvidenceRole.CLAIM),
            ("E1/es/1", EvidenceRole.CONTEXT),
        ]
        assert f.severity == (2 if "closed" in expected else 3)


def test_one_flag_per_cue_with_every_broken_rule() -> None:
    flags = run_check(Readability(["es"]), _tl([(0, 10, "a" * 43)]), "run_1", PB)
    assert len(flags) == 1
    f = flags[0]
    assert f.title == (
        "Cue 1: 43 characters/line (max 42); reading speed 103.2 CPS (max 17); "
        "duration 0.42 s (min 5/6 s)"
    )
    assert (f.check, f.lang, f.confidence, f.tier) == (
        "loc.readability",
        "es",
        1.0,
        Tier.MUST_REVIEW,
    )
    claim = f.evidence[0]
    assert (claim.ref, claim.role, claim.quote, claim.frames) == (
        "E1/es/1",
        EvidenceRole.CLAIM,
        "a" * 43,
        (0, 10),
    )
    assert claim.tc_in is None  # display fields come from the timeline span (none set here)


def test_recheck_reproduces_only_on_unchanged_timeline() -> None:
    check = Readability(["es"])
    tl = _tl([(0, 10, OK_TEXT)])
    (flag,) = run_check(check, tl, "run_1", PB)
    assert check.recheck(flag, tl)
    assert not check.recheck(flag, _tl([(0, 48, OK_TEXT)]))  # fixed cue
    assert not check.recheck(flag, _tl([(0, 11, OK_TEXT)]))  # different violation text
