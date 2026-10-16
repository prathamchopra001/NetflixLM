"""loc.shot_change (2.4): cue in/out points 1..11 frames from a cut, at 24/1 and 24000/1001."""

from fractions import Fraction

import pytest

from nip.agents.base import Input, run_check
from nip.agents.localization import CHECKS
from nip.agents.localization.shot_change import ShotChange, window_frames
from nip.contracts.flag import EvidenceKind, EvidenceRole, ProducedBy, Tier
from nip.contracts.timeline import Span, Timeline

PB = ProducedBy(model_variant=None, plan_id="plan_1")
CUTS = [240, 480, 720]  # first frames of shots 1..3; shot 0 starts at 0 (not a cut)


def tl(
    cues: list[tuple[int, int]], fps: tuple[int, int] = (24, 1), cuts: list[int] = CUTS
) -> Timeline:
    edges = [0, *cuts, 1000]
    spans = [
        Span(kind=EvidenceKind.SHOT, ref=f"E1/shot/{i}", frames=(a, b))
        for i, (a, b) in enumerate(zip(edges, edges[1:], strict=False))
    ]
    spans += [
        Span(
            kind=EvidenceKind.SUBTITLE_CUE, ref=f"E1/es/{i}", frames=f, lang="es", text=f"Hola {i}"
        )
        for i, f in enumerate(cues, 1)
    ]
    return Timeline(episode="E1", fps=fps, duration_frames=1000, spans=spans)


def titles(t: Timeline) -> list[str]:
    return [f.title for f in run_check(ShotChange(["es"]), t, "run_1", PB)]


def test_window_is_less_than_half_a_second_of_the_probed_rate() -> None:
    rates = [(24, 1), (24000, 1001), (25, 1), (30, 1)]
    assert [window_frames(Fraction(*f), Fraction(1, 2)) for f in rates] == [11, 11, 12, 14]


@pytest.mark.parametrize("fps", [(24, 1), (24000, 1001)])
@pytest.mark.parametrize(
    ("cue", "expected"),
    [
        ((243, 300), ["in-point 3 frames after the cut at"]),  # starts 3 frames after a cut
        ((237, 300), ["in-point 3 frames before the cut at"]),
        ((250, 300), ["in-point 10 frames after"]),
        ((251, 300), ["in-point 11 frames after"]),  # 11 is inside the window
        ((252, 300), []),  # 12 frames = 1/2 s: outside
        ((240, 300), []),  # exactly on the cut: what the rule asks for
        ((100, 235), ["out-point 5 frames before the cut at"]),
        ((100, 245), ["out-point 5 frames after the cut at"]),
        ((100, 240), []),  # ends on the cut
        ((100, 300), []),  # crosses a cut: not this rule
        ((243, 477), ["in-point 3 frames after", "out-point 3 frames before"]),
    ],
)
def test_planted_cases(cue: tuple[int, int], expected: list[str], fps: tuple[int, int]) -> None:
    got = titles(tl([cue], fps))
    if not expected:
        assert got == []
    else:
        assert len(got) == 1 and all(e in got[0] for e in expected)


def test_first_shot_start_is_not_a_cut() -> None:
    assert titles(tl([(3, 60)])) == []


def test_flag_cites_the_cue_and_the_cut() -> None:
    (flag,) = run_check(ShotChange(["es"]), tl([(100, 235)]), "run_1", PB)
    assert (flag.check, flag.lang, flag.tier, flag.confidence) == (
        "loc.shot_change",
        "es",
        Tier.MUST_REVIEW,
        1.0,
    )
    assert [(e.ref, e.role) for e in flag.evidence] == [
        ("E1/es/1", EvidenceRole.CLAIM),
        ("E1/shot/1", EvidenceRole.CONTEXT),
    ]
    assert flag.evidence[0].frames == (100, 235) and flag.evidence[1].frames == (240, 480)


def test_windows_of_20_cues_each_find_their_own_cuts() -> None:
    cues = [(30 * i, 30 * i + 20) for i in range(25)]  # cue 22 (i=21) ends at 650
    t = tl(cues, cuts=[654])
    check = ShotChange(["es"])
    assert [u.key for u in check.units(t)] == ["E1/es/1-20", "E1/es/21-25"]
    assert [f.title.split(" frames")[0] for f in run_check(check, t, "run_1", PB)] == [
        "Cue 22: out-point 4",
        "Cue 23: in-point 6",  # a cut between two cues is close to both
    ]


def test_recheck_passes_then_fails_after_the_cue_moves() -> None:
    check = ShotChange(["es"])
    t = tl([(243, 300)])
    (flag,) = run_check(check, t, "run_1", PB)
    assert check.recheck(flag, t) is True
    moved = tl([(240, 300)])
    assert check.recheck(flag, moved) is False
    assert check.recheck(flag, tl([(243, 300)], cuts=[])) is False


def test_needs_the_picture_and_target_subs() -> None:
    assert ShotChange in CHECKS
    assert not ShotChange.active({Input.TARGET_SUBS, Input.SOURCE_SUBS, Input.SCRIPT})
    assert not ShotChange.active({Input.PICTURE})
    assert ShotChange.active({Input.PICTURE, Input.TARGET_SUBS})


def test_unit_context_holds_the_cuts_of_the_window_only() -> None:
    check = ShotChange(["es"])
    (u,) = check.units(tl([(100, 150), (700, 760)]))
    assert [s.ref for s in u.context] == ["E1/shot/1", "E1/shot/2", "E1/shot/3"]
    assert check.units(tl([(100, 150)]))[0].context == ()
    assert [s.ref for s in check.units(tl([(230, 250)]))[0].context] == ["E1/shot/1"]
