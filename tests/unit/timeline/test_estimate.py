from fractions import Fraction
from pathlib import Path

import pytest

from nip.contracts.flag import EvidenceKind
from nip.ingest import parse_fountain, parse_srt
from nip.ingest.media import MediaInfo
from nip.ingest.script import Element, Scene, Script
from nip.timecode import ms_to_frame, smpte_to_frame
from nip.timeline.estimate import build_timeline, scene_bounds, scene_lines

FIXTURES = Path(__file__).parents[2] / "fixtures" / "ingest"
NTSC_FILM = Fraction(24000, 1001)


def _actions(no: str, n: int, last: str = "x") -> Scene:
    """A scene of a heading and n one-line actions (the last one's text is `last`)."""
    els = [Element("action", "x") for _ in range(n - 1)] + [Element("action", last)]
    return Scene(no, f"INT. ROOM {no} - DAY", els)


def _media(fps: Fraction, frames: int, start_tc: int = 0) -> MediaInfo:
    return MediaInfo("x.mkv", fps, frames, 1920, 1080, "h264", "yuv420p", start_tc, False, 1)


def test_scene_lines_screenplay_layout() -> None:
    scene = Scene(
        "1",
        "INT. HARBOR WAREHOUSE - NIGHT",
        [
            Element("action", "Maya enters."),  # blank + 1
            Element("parenthetical", "whispering", "MAYA"),  # blank + cue + 1
            Element("dialogue", "Where is he?", "MAYA"),  # same speech: + 1
            Element("dialogue", "Behind you.", "LEO"),  # new speaker: blank + cue + 1
            Element("action", "a" * 130),  # blank + 3 lines at 60 columns
            Element("dialogue", "b" * 36, "LEO"),  # after action: blank + cue + 2 lines at 35
            Element("transition", "CUT TO:"),  # blank + 1
        ],
    )
    assert scene_lines(scene) == 2 + 2 + 3 + 1 + 3 + 4 + 4 + 2


def test_scene_lines_counts_explicit_newlines() -> None:
    assert scene_lines(_actions("1", 1, "line one\nline two")) == 2 + 1 + 2


@pytest.mark.parametrize(("fps", "page_frames"), [(Fraction(24), 1440), (Fraction(25), 1500)])
def test_one_page_is_one_minute(fps: Fraction, page_frames: int) -> None:
    # 26 + 29 = 55 printed lines = one page
    script = Script(None, [_actions("1", 12), _actions("2", 13, "x\ny")])
    assert [scene_lines(s) for s in script.scenes] == [26, 29]
    assert scene_bounds(script, fps) == [0, round(Fraction(26, 55) * page_frames), page_frames]


def test_bounds_come_from_cumulative_lines_at_ntsc_rate() -> None:
    script = Script(None, [_actions(str(i), 1) for i in range(1, 101)])  # 100 x 4 lines
    b = scene_bounds(script, NTSC_FILM)
    assert b == [ms_to_frame(Fraction(4 * i * 60_000, 55), NTSC_FILM) for i in range(101)]
    assert all(x < y for x, y in zip(b, b[1:], strict=False))
    assert b[-1] == 10462  # 400/55 min = 436.36 s at 23.976 fps


def test_build_timeline_from_fixtures_with_media() -> None:
    script = parse_fountain((FIXTURES / "sample.fountain").read_bytes()).data
    subs = parse_srt((FIXTURES / "sample.srt").read_bytes()).data
    assert script and subs
    start = smpte_to_frame("01:00:00:00", NTSC_FILM)
    tl = build_timeline(
        "S01E03", script, _media(NTSC_FILM, 100_000, start), {"es-419": subs}, [(0, 30), (30, 90)]
    )
    assert tl.source == "script_estimate" and tl.fps == (24000, 1001)
    assert tl.duration_frames == 100_000 and tl.start_tc_frames == start

    scenes, bounds = tl.of(EvidenceKind.SCENE), scene_bounds(script, NTSC_FILM)
    assert [s.ref for s in scenes] == ["S01E03/sc/12A", "S01E03/sc/2", "S01E03/sc/3"]
    assert [s.frames for s in scenes] == [(a, b) for a, b in zip(bounds, bounds[1:], strict=False)]
    assert scenes[0].scene == "S01E03 · Sc 12A (script estimate)" and scenes[0].tc_in is None

    cue = tl.resolve("S01E03/es-419/1")
    assert cue and cue.kind is EvidenceKind.SUBTITLE_CUE and cue.lang == "es-419"
    assert cue.frames == (ms_to_frame(1000, NTSC_FILM), ms_to_frame(2500, NTSC_FILM)) == (24, 60)
    assert (cue.tc_in, cue.tc_out) == ("01:00:01:00", "01:00:02:12")
    assert cue.text == "Hello there\nsecond line" and cue.scene is None

    shot = tl.resolve("S01E03/shot/1")
    assert shot and shot.frames == (30, 90) and shot.tc_in == "01:00:01:06"
    assert tl.resolve("S01E03/es-419/3") is None
    assert tl.resolve("S01E04/sc/12A") is None
    assert [c.ref for c in tl.of(EvidenceKind.SUBTITLE_CUE, "en")] == []


def test_scenes_past_the_end_of_the_picture() -> None:
    script = Script(None, [_actions("1", 1), _actions("2", 1), _actions("3", 1)])  # 4 lines each
    b = scene_bounds(script, Fraction(24))  # [0, 105, 209, 314]
    tl = build_timeline("E1", script, _media(Fraction(24), 150))
    assert [s.frames for s in tl.of(EvidenceKind.SCENE)] == [(0, b[1]), (b[1], 150), None]
    assert tl.resolve("E1/sc/3") is not None  # still citable, just not on the frame axis


def test_without_picture_uses_24_fps_and_covers_every_object() -> None:
    script = Script(None, [_actions("1", 1)])  # 4 lines -> 105 frames
    subs = parse_srt("1\n00:00:10,000 --> 00:00:10,020\nlate and tiny\n").data
    assert subs
    tl = build_timeline("E1", script, subtitles={"en": subs})
    assert tl.fps == (24, 1) and tl.start_tc_frames == 0
    assert tl.resolve("E1/en/1").frames == (240, 241)  # type: ignore[union-attr]  # >= 1 frame
    assert tl.duration_frames == 241


def test_duplicate_scene_numbers_are_ambiguous() -> None:
    with pytest.raises(ValueError, match="duplicate timeline refs"):
        build_timeline("E1", Script(None, [_actions("5", 1), _actions("5", 1)]))


def test_keyframes_are_one_frame_spans() -> None:
    script = Script(None, [_actions("1", 1)])
    tl = build_timeline(
        "E1", script, _media(Fraction(24), 100), shots=[(0, 40), (40, 100)], keyframes=[(1, 0, 70)]
    )
    kf = tl.resolve("E1/kf/1.0")
    assert kf and kf.kind is EvidenceKind.KEYFRAME and kf.frames == (70, 71)
    assert kf.tc_in == "00:00:02:22"
