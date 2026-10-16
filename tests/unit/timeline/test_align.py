from fractions import Fraction

import pytest

from nip.contracts.flag import EvidenceKind
from nip.ingest.script import Element, Scene, Script
from nip.timeline.align import (
    align,
    align_lines,
    align_tokens,
    normalize,
    place_scenes,
    segment_lines,
    with_picture_timing,
)
from nip.timeline.asr import TranscriptSegment, TranscriptWord

FPS = Fraction(24)


def seg(text: str, start: int, per_word: int = 6) -> TranscriptSegment:
    """One segment: `text` spoken from frame `start`, `per_word` frames per word."""
    words = tuple(
        TranscriptWord(w, start + i * per_word, start + (i + 1) * per_word, 0.9)
        for i, w in enumerate(text.split())
    )
    return TranscriptSegment((words[0].f_in, words[-1].f_out), "en", text, words)


def script(*scenes: list[str]) -> Script:
    """Scenes of dialogue lines; a line starting with '>' is an action line."""
    return Script(
        None,
        [
            Scene(
                str(i + 1),
                f"INT. ROOM {i + 1} - DAY",
                [
                    Element("action", x[1:]) if x.startswith(">") else Element("dialogue", x, "A")
                    for x in lines
                ],
            )
            for i, lines in enumerate(scenes)
        ],
    )


LINES = [
    "You're a jerk, Thom.",
    "Look Celia, we have to follow our passions",
    "Why don't you just admit that you're freaked out by my robot hand",
    "I'm not freaked out",
]
TRANSCRIPT = [
    seg("you're a jerk thom", 100),
    seg("look celia we have to follow our passions", 200),
    seg("why don't you just admit that you're freaked out by my robot hand", 330),
    seg("i'm not freaked out", 500),
]
STARTS = [100, 200, 330, 500]


def test_normalize():
    assert normalize("You’re a JERK, Thom...") == ["youre", "a", "jerk", "thom"]
    assert normalize("— ... !") == []


@pytest.mark.parametrize("fn", [align_tokens, align_lines])
def test_matchers_place_every_line_at_its_first_word(fn):
    got = fn(script(LINES), TRANSCRIPT)
    assert [got[(0, i)].frames[0] for i in range(4)] == STARTS


@pytest.mark.parametrize("fn", [align_tokens, align_lines])
def test_matchers_survive_asr_errors(fn):
    noisy = [
        seg("you're a jerk tom", 100),  # one substitution
        seg("look celia we have to follow our passion", 200),
        seg("why don't you just admit you are freaked out by my robot hand", 330),
        seg("i'm not freaked out", 500),
    ]
    got = fn(script(LINES), noisy)
    assert [got[(0, i)].frames[0] for i in range(4)] == STARTS


@pytest.mark.parametrize("fn", [align_tokens, align_lines])
def test_line_absent_from_audio_is_unplaced_and_does_not_shift_others(fn):
    s = script(LINES[:2] + ["This line was cut from the film entirely"] + LINES[2:])
    got = fn(s, TRANSCRIPT)
    assert (0, 2) not in got
    assert got[(0, 3)].frames[0] == 330 and got[(0, 4)].frames[0] == 500


@pytest.mark.parametrize("fn", [align_tokens, align_lines])
def test_repeated_line_is_matched_in_script_order(fn):
    s = script(["yes", "no way", "yes"])
    tr = [seg("yes", 10), seg("no way", 100), seg("yes", 300)]
    got = fn(s, tr)
    assert [got[(0, i)].frames[0] for i in range(3)] == [10, 100, 300]


def test_token_variant_ignores_scattered_stopword_hits():
    # "the" and "you" occur all over the transcript; they must not place the line
    tr = [seg("the cat saw you and the dog and you ran", 0, 24)]
    assert align_tokens(script(["you the one who knows"]), tr) == {}


def test_place_scenes_snaps_start_to_latest_cut_before_first_line_and_tiles():
    s = script(["a"], ["b"])
    lines = align_tokens(s, [seg("a", 100), seg("b", 400)])
    shots = [(0, 90), (90, 250), (250, 390), (390, 600)]
    p = place_scenes(s, lines, shots, 600)
    assert [x.frames for x in p] == [(90, 390), (390, 600)]  # b starts at the cut before frame 400
    assert all(x.in_cut for x in p)


def test_place_scenes_never_starts_after_the_first_line():
    s = script(["a"])
    lines = align_tokens(s, [seg("a", 100)])
    p = place_scenes(s, lines, [(0, 130), (130, 200)], 200)
    assert p[0].frames == (0, 130)  # starts at cut 0, not the cut at 130 inside the speech


def test_scene_with_dialogue_but_no_anchor_is_not_in_cut_and_action_scene_is_filled():
    s = script(
        ["hello there"],
        ["this long speech never happens anywhere in the cut at all"],
        [">She waits."],
        ["goodbye now"],
    )
    lines = align_tokens(s, [seg("hello there", 100), seg("goodbye now", 700)])
    p = place_scenes(s, lines, [(0, 300), (300, 450), (450, 600), (600, 800)], 800)
    assert p[1].frames is None and not p[1].in_cut
    assert p[2].in_cut and p[2].frames is not None
    assert p[0].frames[1] <= p[2].frames[0] < p[2].frames[1] <= p[3].frames[0]


def test_with_picture_timing_replaces_estimate_labels():
    from nip.timeline.estimate import build_timeline

    s = script(["hello there"], ["this long speech never happens anywhere in the cut at all"])
    res = align(s, [seg("hello there", 48)], [(0, 24), (24, 100)], 100)
    tl = with_picture_timing(build_timeline("EP1", s), s, res)
    sc1, sc2 = tl.of(EvidenceKind.SCENE)
    assert tl.source == "picture"
    assert sc1.frames == res.scenes[0].frames and sc1.scene is None
    assert sc1.tc_in == "00:00:01:00"  # the cut at frame 24, fps 24
    assert sc2.frames is None and "not in cut" in (sc2.scene or "")


def test_segment_lines_picks_the_most_overlapping_line():
    s = script(LINES)
    res = align(s, TRANSCRIPT, [(0, 600)], 600)
    assert segment_lines(res, TRANSCRIPT) == [(0, 0), (0, 1), (0, 2), (0, 3)]
    assert segment_lines(res, [seg("noise", 5000)]) == [None]


def test_short_unmatched_scene_stays_in_cut_and_shares_the_gap():
    s = script(["hello there"], ["Scales!"], ["goodbye now"])
    lines = align_tokens(s, [seg("hello there", 100), seg("goodbye now", 700)])
    p = place_scenes(s, lines, [(0, 400), (400, 800)], 800)
    assert p[1].in_cut  # an ASR miss, not a cut scene; no gap, so no frames
