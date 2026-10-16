"""The 2.4 benchmark driver pure parts: which flags a check is scored on, self-labelled natives."""

from eval.exp.loc_bench import native_label, scope_flags, stub_plan
from eval.metrics import match


def flag(
    check: str, lang: str, ref: str = "S01E01/es/3", frames: tuple[int, int] = (10, 20)
) -> dict:  # type: ignore[type-arg]
    return {
        "check": check,
        "lang": lang,
        "title": f"{check} {lang}",
        "evidence": [
            {"kind": "subtitle_cue", "ref": ref, "role": "claim", "frames": list(frames)},
            {"kind": "shot", "ref": "S01E01/shot/1", "role": "context", "frames": [0, 5]},
        ],
    }


def test_term_and_shot_change_only_on_the_injected_languages() -> None:
    flags = [
        flag("loc.term", "es"),
        flag("loc.term", "fr"),
        flag("loc.shot_change", "es"),
        flag("loc.shot_change", "de"),
        flag("loc.drift", "fr"),  # whole-track checks: every language
        flag("loc.offset", "it"),
        flag("loc.readability", "es"),  # not one of ours
    ]
    injected: dict[str, set[str | None]] = {"loc.term": {"es"}, "loc.shot_change": {"es"}}
    kept = [(f["check"], f["lang"]) for f in scope_flags(flags, injected)]
    assert kept == [
        ("loc.term", "es"),
        ("loc.shot_change", "es"),
        ("loc.drift", "fr"),
        ("loc.offset", "it"),
    ]


def test_native_label_is_the_claimed_cue_and_matches_its_flag() -> None:
    f = flag("loc.shot_change", "es", "S01E01/es/12", (300, 340))
    lb = native_label(f, "sintel")
    assert (lb.check, lb.lang, lb.episode, lb.target.refs, lb.target.frames) == (
        "loc.shot_change", "es", "S01E01", ["S01E01/es/12"], (300, 340),
    )  # fmt: skip
    assert lb.injector == "native-clean-run" and "clean-run flag" in lb.description


def test_stub_plan_is_a_valid_plan() -> None:
    plan, inv = stub_plan()
    assert plan.decisions == {} and inv.nodes == []
    assert match([], []) == []
