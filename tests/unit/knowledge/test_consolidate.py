"""Consolidation rules (data-model.md › Knowledge layer): one test per interval rule + merging."""

from typing import Any

import pytest

from nip.knowledge import consolidate as c
from nip.knowledge.consolidate import Event, Pos, consolidate

# scenes 1..6 in story order; scene s is screen frames [100*s, 100*s + 50) of episode_seq 1001
POS = {s: Pos(s, ((1001 << 32) | 100 * s, (1001 << 32) | (100 * s + 50))) for s in range(1, 7)}
MAYA, LEO, KEY, WAREHOUSE, SECRET = 1, 2, 10, 20, 30
_ids = iter(range(1, 1000))


def ev(
    scene: int, pred: str, subj: int, obj: int | None = None, conf: float = 0.9, **value: Any
) -> Event:
    return Event(next(_ids), scene, pred, subj, obj, value or None, conf)


def facts(events: list[Event], pos: dict[int, Pos] = POS) -> list[tuple[Any, ...]]:
    out = consolidate(events, pos, show_id=1)
    return sorted((f.predicate, f.subject_id, f.object_id, f.story, f.value) for f in out)


def test_present_at_is_the_scene_range_and_same_scene_repeats_merge() -> None:
    out = consolidate(
        [
            ev(2, "present_at", MAYA, WAREHOUSE),
            ev(2, "present_at", MAYA, WAREHOUSE),
            ev(4, "present_at", MAYA, WAREHOUSE),
        ],
        POS,
        1,
    )
    assert [(f.story, len(f.source_event_ids)) for f in out] == [((2, 3), 2), ((4, 5), 1)]
    assert out[0].screen == POS[2].screen


def test_learns_and_dead_are_open_ended_and_overlap_merges() -> None:
    got = facts(
        [
            ev(2, "learns", MAYA, SECRET),
            ev(5, "learns", MAYA, SECRET),
            ev(3, "state", LEO, state="dead"),
        ]
    )
    assert got == [
        ("learns", MAYA, SECRET, (2, None), None),
        ("state", LEO, None, (3, None), {"state": "dead"}),
    ]
    [learn] = [f for f in consolidate([ev(2, "learns", MAYA, SECRET)], POS, 1)]
    assert learn.screen == (POS[2].screen[0], None)


def test_holds_continues_for_the_holder_until_another_holder() -> None:
    got = facts(
        [
            ev(1, "holds", MAYA, KEY, event="obtain"),
            ev(2, "holds", MAYA, KEY, event="use"),
            ev(4, "holds", LEO, KEY, event="obtain"),
        ]
    )
    assert got == [
        ("holds", MAYA, KEY, (1, 4), {"event": "obtain"}),
        ("holds", LEO, KEY, (4, None), {"event": "obtain"}),
    ]


def test_holds_ends_when_given_away_or_destroyed() -> None:
    lost = facts(
        [ev(1, "holds", MAYA, KEY, event="obtain"), ev(3, "holds", MAYA, KEY, event="lose")]
    )
    assert lost == [
        ("holds", MAYA, KEY, (1, 3), {"event": "obtain"}),
        ("state", KEY, None, (3, None), {"state": "lost"}),  # ruling (2.3 review I-1)
    ]
    gone = facts(
        [ev(1, "holds", MAYA, KEY, event="obtain"), ev(5, "state", KEY, state="destroyed")]
    )
    assert gone[0] == ("holds", MAYA, KEY, (1, 5), {"event": "obtain"})
    assert gone[1] == ("state", KEY, None, (5, None), {"state": "destroyed"})


def test_superseding_event_in_the_same_scene_keeps_one_unit() -> None:
    got = facts(
        [ev(2, "holds", MAYA, KEY, event="obtain"), ev(2, "holds", MAYA, KEY, event="give")]
    )
    assert got == [("holds", MAYA, KEY, (2, 3), {"event": "obtain"})]


def test_injured_lasts_until_healed_and_dead_ends_it() -> None:
    got = facts(
        [
            ev(1, "state", MAYA, state="injured", detail="left hand cut"),
            ev(3, "state", MAYA, state="healed"),
            ev(4, "state", LEO, state="injured"),
            ev(6, "state", LEO, state="dead"),
        ]
    )
    assert got == [
        ("state", MAYA, None, (1, 3), {"state": "injured", "detail": "left hand cut"}),
        ("state", MAYA, None, (3, None), {"state": "healed"}),
        ("state", LEO, None, (4, 6), {"state": "injured"}),
        ("state", LEO, None, (6, None), {"state": "dead"}),
    ]


def test_relationship_changes_kind_and_wearing_ends_on_remove() -> None:
    got = facts(
        [
            ev(1, "relationship", MAYA, LEO, kind="strangers"),
            ev(2, "relationship", MAYA, LEO, kind="strangers"),
            ev(4, "relationship", MAYA, LEO, kind="partners"),
            ev(2, "wearing", MAYA, KEY),
            ev(5, "wearing", MAYA, KEY, event="remove"),
        ]
    )
    assert got == [
        ("relationship", MAYA, LEO, (1, 4), {"kind": "strangers"}),
        ("relationship", MAYA, LEO, (4, None), {"kind": "partners"}),
        ("wearing", MAYA, KEY, (2, 5), None),
    ]


def test_flashback_order_follows_story_not_screen() -> None:
    # scene 6 is a flashback: first in story order, last on screen
    pos = dict(POS) | {6: Pos(0, POS[6].screen)}
    got = facts(
        [ev(6, "holds", MAYA, KEY, event="obtain"), ev(2, "holds", LEO, KEY, event="obtain")], pos
    )
    assert got == [
        ("holds", MAYA, KEY, (0, 2), {"event": "obtain"}),
        ("holds", LEO, KEY, (2, None), {"event": "obtain"}),
    ]
    [maya] = [
        f
        for f in consolidate(
            [ev(6, "holds", MAYA, KEY, event="obtain"), ev(2, "holds", LEO, KEY, event="obtain")],
            pos,
            1,
        )
        if f.subject_id == MAYA
    ]
    assert maya.screen == POS[6].screen  # superseded earlier on screen: its own scene's end


def test_no_two_active_facts_overlap_per_subject_predicate_object() -> None:
    events = [
        ev(s, p, MAYA, o, event="use")
        for s in range(1, 7)
        for p, o in (("holds", KEY), ("present_at", WAREHOUSE), ("learns", SECRET))
    ]
    out = consolidate(events, POS, 1)
    for a in out:
        for b in out:
            same = (a.subject_id, a.predicate, a.object_id) == (
                b.subject_id,
                b.predicate,
                b.object_id,
            )
            if a is not b and same:
                assert a.story[1] is not None and b.story[1] is not None
                assert a.story[1] <= b.story[0] or b.story[1] <= a.story[0]


def test_confidence_is_the_minimum_reduced_when_story_position_is_inferred(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(c, "INFERRED_FACTOR", 0.5)
    pos = dict(POS) | {3: Pos(3, POS[3].screen, inferred=True)}
    out = consolidate(
        [
            ev(2, "learns", MAYA, SECRET, conf=0.9),
            ev(3, "learns", MAYA, SECRET, conf=0.7),
            ev(4, "decision", LEO, conf=0.8, detail="leave"),
        ],
        pos,
        1,
    )
    assert sorted(f.confidence for f in out) == [0.35, 0.8]


def test_a_lost_object_ends_its_holder_and_a_use_stays_inside_the_holders_fact() -> None:
    out = consolidate(
        [
            ev(1, "holds", MAYA, KEY, event="obtain"),
            ev(2, "holds", MAYA, KEY, event="use"),
            ev(3, "state", KEY, state="lost"),
        ],
        POS,
        1,
    )
    [hold] = [f for f in out if f.predicate == "holds"]
    assert hold.story == (1, 3) and len(hold.source_event_ids) == 2  # 2.3 reads the use event


def test_state_lost_is_a_fact_and_a_later_state_ends_it() -> None:  # ruling (2.3 review I-1)
    got = facts(
        [
            ev(1, "holds", MAYA, KEY, event="obtain"),
            ev(2, "state", KEY, state="lost"),
            ev(4, "holds", LEO, KEY, event="drop"),
            ev(5, "state", KEY, state="destroyed"),
        ]
    )
    assert got == [
        ("holds", MAYA, KEY, (1, 2), {"event": "obtain"}),
        ("state", KEY, None, (2, 5), {"state": "lost"}),  # the drop at 4 merges into it
        ("state", KEY, None, (5, None), {"state": "destroyed"}),
    ]
