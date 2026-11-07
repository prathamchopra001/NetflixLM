"""The ambiguous-transitions variant of the synthetic show and EXP-007's helpers."""

import re
from pathlib import Path
from typing import Any

import pytest

from eval.exp.exp007_story import arm_show, run_arm, story_metrics, truth_positions, truth_relation
from eval.synthetic import build, read_show, write_show
from eval.synthetic.ambiguous import YEAR_WORDS, ambiguate
from eval.synthetic.model import find_mentions, truth
from eval.synthetic.rules import violations
from nip.contracts import refs
from nip.ingest import parse_fountain
from nip.knowledge.story import Verdict


@pytest.fixture(scope="module")
def shows(tmp_path_factory: pytest.TempPathFactory) -> dict[int, Path]:
    out = {}
    for seed in (1, 3):
        d = tmp_path_factory.mktemp(f"amb{seed}")
        write_show(build(seed, ambiguous=True), d)
        out[seed] = d
    return out


class CueReader:
    """What a careful reader does with the prose cues alone (no knowledge of the truth)."""

    def complete(self, prompt: str, schema: Any, **kw: Any) -> Verdict:
        second = prompt.split("SECOND scene:\n", 1)[1]
        if m := re.search(r"(\w+) years ago", second):
            return Verdict(relation="earlier", days=365 * YEAR_WORDS.index(m[1].lower()))
        if re.search(r"At the same moment|Meanwhile|Across the harbor", second):
            return Verdict(relation="simultaneous")
        return Verdict(relation="next_day")


def test_default_build_is_unchanged_and_ambiguous_is_deterministic() -> None:
    clean = truth(build(1))
    assert truth(build(1, ambiguous=False)) == clean
    assert truth(build(1, ambiguous=True)) == truth(build(1, ambiguous=True)) != clean
    assert truth(build(2, ambiguous=True)) != truth(build(1, ambiguous=True))


def test_scripts_parse_truth_is_consistent_and_the_show_stays_clean(shows: dict[int, Path]) -> None:
    for d in shows.values():
        show = read_show(d)
        for ep, scenes in show.episodes.items():
            parsed = parse_fountain((d / f"{ep}.fountain").read_bytes())
            assert parsed.ok and parsed.data and not parsed.warnings
            assert [s.heading for s in parsed.data.scenes] == [sc.heading for sc in scenes]
            for sc in scenes:
                for ln in sc.lines:
                    assert all(f.quote in ln.text for f in ln.facts)
                    assert sorted(m.model_dump_json() for m in ln.mentions) == sorted(
                        m.model_dump_json() for m in find_mentions(show.entities, ln.text)
                    )
        assert violations(show) == []  # flashbacks and simultaneous scenes are still exempt


def test_story_time_is_not_stated_where_the_rules_look(shows: dict[int, Path]) -> None:
    from eval.exp.exp007_story import load_scenes

    d = shows[1]
    show = read_show(d)
    res = run_arm("rules", d)
    flash = {
        refs.scene(e, s.no)
        for e, ss in show.episodes.items()
        for s in ss
        if s.marker == "flashback"
    }
    assert len(flash) == 8
    assert all("flashback" not in p["markers"] for p in res["positions"])
    assert res["ambiguous"] > 20
    assert story_metrics(show, {}, res)["story/tau"] < 0.95
    assert len(load_scenes(d)) == 150


def test_the_prose_cues_are_enough_to_order_the_show(shows: dict[int, Path]) -> None:
    d = shows[1]  # seed 1 has no silent case (a heading that cannot go back)
    show = read_show(d)
    res = run_arm("llm", d, CueReader())
    m = story_metrics(show, {}, res)
    assert m["story/tau"] == 1.0
    assert m["story/flashback_recall"] == m["story/simultaneous_recall"] == 1.0
    assert res["llm_calls"] == res["ambiguous"]
    # truth relation of each asked transition is what the reader answered, except unmarked "later"
    assert m["story/verdict_acc"] > 0.9


def test_silent_cases_are_marked_and_the_reader_cannot_fix_them(shows: dict[int, Path]) -> None:
    show, notes = ambiguate(build(3), 3)
    assert any(k.endswith("silent") for k in notes.values())
    d = shows[3]
    res = run_arm("llm", d, CueReader())
    assert story_metrics(read_show(d), notes, res)["story/tau"] < 1.0


def test_truth_arm_scores_perfectly_and_arm_show_swaps_the_order(shows: dict[int, Path]) -> None:
    show = read_show(shows[1])
    m = story_metrics(show, {}, truth_positions(show), truth_arm=True)
    assert m["story/tau"] == m["story/day_acc_present"] == m["story/flashback_precision"] == 1.0
    res = run_arm("rules", shows[1])
    swapped = arm_show(show, res)
    assert [s.story_seq for s in swapped.episodes["S01E01"]] == [
        p["story_seq"] for p in res["positions"][:25]
    ]
    assert all(s.marker is None for ss in swapped.episodes.values() for s in ss)  # none detected
    assert truth_relation(show, "S01E01/sc/2") in ("same_day", "next_day")
