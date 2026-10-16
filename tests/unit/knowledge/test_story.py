"""Story order and story days (2.2): rules on Fountain, overrides, the LLM step with a stub, and
the synthetic show against its truth."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from pydantic import BaseModel

from eval.synthetic.generate import build
from eval.synthetic.model import render_bible, render_fountain
from nip.ingest.bible import StoryOverride, parse_bible
from nip.ingest.script import parse_fountain
from nip.knowledge import story
from nip.knowledge.story import Position, SceneIn, Verdict, derive
from nip.runtime.clients.llm import StubLLM


def scenes(*scripts: str) -> list[SceneIn]:
    """One Fountain script per episode, S01E01, S01E02, ..."""
    out: list[SceneIn] = []
    for n, text in enumerate(scripts, 1):
        parsed = parse_fountain(text)
        assert parsed.data, parsed.errors
        out += story.scenes_from_script(f"S01E{n:02d}", parsed.data)
    return out


def heads(*headings: str) -> list[SceneIn]:
    return scenes("\n\n".join(f"{h}\n\nSomething happens." for h in headings))


def pos(sc: list[SceneIn], ov: list[StoryOverride] = [], llm: Any = None) -> list[Position]:  # noqa: B006
    return derive(sc, ov, llm).positions


def days(p: list[Position]) -> list[int | None]:
    return [x.story_day for x in p]


def seqs(p: list[Position]) -> list[int]:
    return [x.story_seq for x in p]


# ---- day rules ---------------------------------------------------------------------------------
def test_time_of_day_cues_and_next_morning() -> None:
    p = pos(
        heads(
            "INT. A - DAY",
            "INT. B - DUSK",
            "INT. C - NIGHT",
            "INT. D - NEXT MORNING",  # a new day
            "INT. E - NEXT MORNING",  # the same morning, not a third day
            "INT. F - NIGHT",
            "INT. G - THAT NIGHT",
            "INT. H - LATER",
            "INT. I - THE NEXT DAY",
        )
    )
    assert days(p) == [1, 1, 1, 2, 2, 2, 2, 2, 3]
    assert seqs(p) == list(range(1, 10))
    assert not any(x.inferred for x in p)  # every position is stated


def test_continuous_marker_and_multi_day_jumps() -> None:
    p = pos(
        heads(
            "INT. A - DAY",
            "INT. B - CONTINUOUS",
            "INT. C - THREE DAYS LATER",
            "INT. D - A WEEK LATER",
            "INT. E - DAYS LATER",
            "INT. F - MOMENTS LATER",
        )
    )
    assert days(p) == [1, 1, 4, 11, 12, 12]
    assert p[1].markers == ("continuous",) and p[1].story_seq == 2  # its own seq
    assert [x.inferred for x in p] == [False, False, False, False, True, False]  # "DAYS": no count


def test_no_time_of_day_is_inferred_same_day() -> None:
    p = pos(heads("INT. A - DAY", "INT. B", "INT. C - NIGHT"))
    assert days(p) == [1, 1, 1] and [x.inferred for x in p] == [False, True, False]


def test_time_of_day_going_back_defaults_to_next_day_inferred() -> None:
    sc = heads("INT. A - NIGHT", "INT. B - MORNING", "INT. C - DAY")
    sc[0] = SceneIn(sc[0].ref, "INT. A - NIGHT")
    d = derive(sc)
    assert days(d.positions) == [1, 2, 2] and d.ambiguous == 1 and d.llm_calls == 0
    assert [x.inferred for x in d.positions] == [False, True, False]
    assert d.positions[1].source == "rule"


# ---- markers and seq ---------------------------------------------------------------------------
def test_flashback_in_the_heading_is_moved_first_and_leaves_the_day_counter() -> None:
    p = pos(
        heads(
            "INT. A - DAY",
            "INT. B - NIGHT",
            "INT. C - DAY (FLASHBACK)",  # the day counter would go back here
            "INT. D - NIGHT",
            "INT. E - NEXT MORNING",
        )
    )
    assert days(p) == [1, 1, None, 1, 2]
    assert p[2].markers == ("flashback",) and p[2].inferred  # no offset: position not stated
    assert seqs(p) == [2, 3, 1, 4, 5]  # the flashback is first in story order


def test_years_earlier_span_runs_until_present_day() -> None:
    p = pos(
        scenes(
            "INT. A - DAY\n\nMaya waits.\n\nINT. B - DAY\n\nTHREE YEARS EARLIER\n\nMaya laughs.\n\n"
            "INT. C - NIGHT\n\nMaya sings.\n\nINT. D - DAY\n\nPRESENT DAY\n\nMaya is old.\n\n"
            "INT. E - NIGHT\n\nShe sleeps.\n"
        )
    )
    assert [x.markers for x in p] == [(), ("flashback",), ("flashback",), (), ()]
    assert days(p) == [1, 1 - 3 * 365, 1 - 3 * 365, 1, 1]  # D: DAY then DAY, same day
    assert [x.inferred for x in p] == [False, False, False, False, False]  # the offset is stated
    assert seqs(p) == [3, 1, 2, 4, 5]


def test_flashback_transition_starts_a_span_that_ends_with_the_episode() -> None:
    ep1 = (
        "INT. A - DAY\n\nHe nods.\n\nFLASHBACK TO:\n\nINT. B - DAY\n\nA kid runs.\n\n"
        "INT. C - DAY\n\nIt rains.\n"
    )
    ep2 = "INT. D - NIGHT\n\nHe wakes.\n"
    p = pos(scenes(ep1, ep2))
    assert [bool(x.markers) for x in p] == [False, True, True, False]  # episode 2 is the present
    assert days(p) == [1, None, None, 1]  # D (NIGHT) follows A (DAY) in the present
    assert seqs(p) == [3, 1, 2, 4]


def test_intercut_and_same_time_share_the_seq_of_the_scene_before() -> None:
    p = pos(
        scenes(
            "INT. A - NIGHT\n\nA phone rings.\n\nINTERCUT WITH:\n\n"
            "EXT. B - NIGHT\n\nShe answers.\n\n"
            "INT. C - NIGHT (SAME TIME)\n\nA door.\n\nINT. D - NIGHT\n\nSilence.\n"
        )
    )
    assert [x.markers for x in p] == [(), ("intercut",), ("intercut",), ()]
    assert seqs(p) == [1, 1, 1, 2] and days(p) == [1, 1, 1, 1]


def test_dream_and_vision_share_the_scene_before_them() -> None:
    p = pos(
        heads(
            "INT. A - NIGHT",
            "INT. HOUSE - NIGHT (DREAM)",
            "INT. DREAM HOUSE - DAY",  # a place called "dream house" is not a dream
            "INT. B - VISION",
        )
    )
    assert [x.markers for x in p] == [(), ("dream",), (), ("vision",)]
    assert seqs(p) == [1, 1, 2, 2]


def test_story_continues_across_episodes_and_flashbacks_move_across_them() -> None:
    p = pos(
        scenes(
            "INT. A - DAY\n\nx\n\nINT. B - NIGHT\n\nx\n",
            "INT. C - NIGHT\n\nx\n\nINT. D - NEXT MORNING\n\nx\n\nINT. E - DAY (FLASHBACK)\n\nx\n",
        )
    )
    assert days(p) == [1, 1, 1, 2, None]  # episode 2 opens on the same night
    assert seqs(p) == [2, 3, 4, 5, 1]  # E (episode 2) is first of the show


def test_episode_opening_with_a_regression_is_ambiguous_next_day() -> None:
    d = derive(scenes("INT. A - NIGHT\n\nx\n", "INT. B - DAY\n\nx\n"))
    assert days(d.positions) == [1, 2] and d.ambiguous == 1 and d.positions[1].inferred


# ---- overrides ---------------------------------------------------------------------------------
def test_overrides_win_over_every_rule() -> None:
    sc = heads(
        "INT. A - DAY", "INT. B - NIGHT (FLASHBACK)", "INT. C - NEXT MORNING", "INT. D - DAY"
    )
    ov = [
        StoryOverride(scene="S01E01/sc/2", markers=["flashback"], story_day=-5),
        StoryOverride(scene="s1e1 scene 3", story_day=9),  # free-text key; the day moves the chain
        StoryOverride(scene="S01E01/sc/4", markers=["dream"]),  # markers replace the detected
        StoryOverride(scene="S01E09/sc/1", story_day=1),  # matches nothing
    ]
    d = derive(sc, ov)
    p = d.positions
    assert days(p) == [1, -5, 9, 9] and d.unmatched == ["S01E09/sc/1"]
    assert p[1].markers == ("flashback",) and p[1].source == "override" and not p[1].inferred
    assert p[3].markers == ("dream",) and p[3].story_seq == p[2].story_seq  # dream shares seq
    assert [x.source for x in p] == ["rule", "override", "override", "override"]
    assert seqs(p) == [2, 1, 3, 3]  # day -5 sorts first, then day 1, then day 9


def test_override_wins_over_a_detected_flashback() -> None:
    sc = heads("INT. A - DAY", "INT. B - DAY (FLASHBACK)")
    p = pos(sc, [StoryOverride(scene="S01E01/sc/2", markers=["vision"])])
    assert p[1].markers == ("vision",) and p[1].story_seq == 1  # a vision shares, not a flashback


def test_override_flashback_without_a_day_is_first_and_not_inferred() -> None:
    p = pos(
        heads("INT. A - DAY", "INT. B - DAY"),
        [StoryOverride(scene="S01E01/sc/2", markers=["flashback"])],
    )
    assert days(p) == [1, None] and seqs(p) == [2, 1] and not p[1].inferred


def test_override_ref_forms() -> None:
    assert story.override_ref("S01E05/sc/3") == "S01E05/sc/3"
    assert story.override_ref("s1e5 sc 3") == "S01E05/sc/3"
    assert story.override_ref("S01E05, scene 12A") == "S01E05/sc/12A"
    assert story.override_ref("the pier scene") == "the pier scene"


# ---- the LLM step ------------------------------------------------------------------------------
class Scripted:
    """An LLM that answers every ambiguous transition with one verdict, counting its calls."""

    variant = "scripted"

    def __init__(self, relation: str = "next_day", days: int = 1, fail: bool = False) -> None:
        self.v, self.fail, self.prompts = Verdict(relation=relation, days=days), fail, []  # type: ignore[arg-type]
        self.prompts: list[str]

    def complete[M: BaseModel](self, prompt: str, schema: type[M], **kw: Any) -> M:
        assert schema is Verdict and kw["max_tokens"] > 0
        self.prompts.append(prompt)
        if self.fail:
            raise TimeoutError("no model")
        return self.v  # type: ignore[return-value]


AMBIGUOUS = heads("INT. A - NIGHT", "INT. B - DAY", "INT. C - NIGHT", "INT. D - MORNING")


@pytest.mark.parametrize(
    ("relation", "n", "want_days", "want_seqs", "want_markers"),
    [
        ("next_day", 1, [1, 2, 2, 3], [1, 2, 3, 4], ((), (), (), ())),
        ("same_day", 1, [1, 1, 1, 1], [1, 2, 3, 4], ((), (), (), ())),
        ("later_days", 5, [1, 6, 6, 11], [1, 2, 3, 4], ((), (), (), ())),
        ("earlier", 2, [1, -1, 1, -1], [3, 1, 4, 2], ((), ("flashback",), (), ("flashback",))),
        ("simultaneous", 1, [1, 1, 1, 1], [1, 1, 2, 2], ((), ("intercut",), (), ("intercut",))),
    ],
)
def test_llm_verdicts(
    relation: str, n: int, want_days: list[int], want_seqs: list[int], want_markers: tuple[Any, ...]
) -> None:
    d = derive(AMBIGUOUS, llm=Scripted(relation, n))
    assert days(d.positions) == want_days
    assert seqs(d.positions) == want_seqs
    assert tuple(x.markers for x in d.positions) == want_markers
    assert d.ambiguous == 2 and d.llm_calls == 2
    assert [x.source for x in d.positions] == ["rule", "llm", "rule", "llm"]
    assert [x.inferred for x in d.positions] == [False, True, False, True]


def test_stub_llm_gives_the_rule_default() -> None:
    assert days(derive(AMBIGUOUS, llm=StubLLM()).positions) == days(derive(AMBIGUOUS).positions)


def test_one_unit_per_transition_with_neighbouring_scenes_in_the_prompt() -> None:
    keys: list[str] = []

    @contextmanager
    def unit(key: str) -> Iterator[None]:
        keys.append(key)
        yield

    llm = Scripted()
    derive(AMBIGUOUS, llm=llm, unit=unit)
    assert keys == ["S01E01/sc/2", "S01E01/sc/4"]
    first = llm.prompts[0]
    assert "INT. A - NIGHT" in first and "INT. B - DAY" in first and "INT. C - NIGHT" in first
    assert "Both scenes are in the same episode" in first and "story day 1" in first


def test_a_failed_call_leaves_the_rule_default_and_is_not_memoised(caplog: Any) -> None:
    memo: dict[Any, Verdict] = {}
    with caplog.at_level(logging.ERROR):
        d = derive(AMBIGUOUS, llm=Scripted(fail=True), memo=memo)
    assert days(d.positions) == [1, 2, 2, 3] and d.llm_calls == 0 and memo == {}
    assert [x.source for x in d.positions] == [
        "rule"
    ] * 4 and "story unit S01E01/sc/2" in caplog.text


def test_memo_asks_each_prompt_once() -> None:
    llm, memo = Scripted(), {}
    derive(AMBIGUOUS, llm=llm, memo=memo)
    derive(AMBIGUOUS, llm=llm, memo=memo)
    assert len(llm.prompts) == 2 and len(memo) == 2


def test_overridden_scene_never_asks() -> None:
    llm = Scripted()
    derive(AMBIGUOUS, [StoryOverride(scene="S01E01/sc/2", story_day=7)], llm)
    assert len(llm.prompts) == 1  # only sc/4 (sc/3 follows the overridden day 7 without regression)


# ---- confidence and tau ------------------------------------------------------------------------
def test_inferred_confidence_factor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NIP_INFERRED_STORY_CONFIDENCE_FACTOR", raising=False)
    assert story.story_confidence(0.8, False) == 0.8
    assert story.story_confidence(1.0, True) == pytest.approx(0.85)
    monkeypatch.setenv("NIP_INFERRED_STORY_CONFIDENCE_FACTOR", "0.5")
    assert story.story_confidence(0.8, True) == pytest.approx(0.4)


def test_kendall_tau_handles_ties() -> None:
    a = {"x": 1, "y": 2, "z": 2, "w": 3}
    assert story.kendall_tau(a, a) == pytest.approx(1.0)
    assert story.kendall_tau(a, {"x": 3, "y": 2, "z": 2, "w": 1}) == pytest.approx(-1.0)


# ---- the synthetic show ------------------------------------------------------------------------
def synthetic(seed: int = 1) -> tuple[list[SceneIn], list[StoryOverride], dict[str, Any]]:
    show = build(seed)
    sc: list[SceneIn] = []
    for ep in show.episodes:
        parsed = parse_fountain(render_fountain(show, ep))
        assert parsed.data
        sc += story.scenes_from_script(ep, parsed.data)
    bible = parse_bible(render_bible(show))
    assert bible.data
    truth = {f"{ep}/sc/{s.no}": s for ep, ss in show.episodes.items() for s in ss}
    return sc, bible.data.story_overrides, truth


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_synthetic_show_order_against_truth(seed: int, capsys: pytest.CaptureFixture[str]) -> None:
    sc, ov, truth = synthetic(seed)
    want = {r: t.story_seq for r, t in truth.items()}
    with_ov = derive(sc, ov)
    rules = derive(sc)  # no bible: the two flashbacks lose their days
    tau_ov = story.kendall_tau(want, {p.ref: p.story_seq for p in with_ov.positions})
    tau_rules = story.kendall_tau(want, {p.ref: p.story_seq for p in rules.positions})
    with capsys.disabled():
        print(
            f"\nstory order, synthetic seed {seed}: tau {tau_ov:.4f} (overrides), "
            f"{tau_rules:.4f} (rules only)"
        )
    assert tau_ov == 1.0
    assert all(p.story_day == truth[p.ref].story_day for p in with_ov.positions)
    assert tau_rules > 0.99
    # the rules know the days of every present scene and only miss the two flashbacks' days
    assert [p.ref for p in rules.positions if p.story_day != truth[p.ref].story_day] == [
        r for r, t in truth.items() if t.marker == "flashback"
    ]
    assert {p.ref for p in rules.positions if p.inferred} == {
        r for r, t in truth.items() if t.marker == "flashback"
    }
    same_time = {r for r, t in truth.items() if t.marker == "same_time"}
    assert {p.ref for p in with_ov.positions if "intercut" in p.markers} == same_time
