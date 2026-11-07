"""Plot Layer 1 injectors: planted lines are exactly the lines the reference rules flag."""

from pathlib import Path

import pytest

from eval.injectors import get, write_labels
from eval.injectors.base import Label
from eval.metrics import load_labels, match
from eval.synthetic import build, read_show, write_show
from eval.synthetic.model import line_ref
from eval.synthetic.rules import violations
from nip.contracts import Flag
from nip.ingest import parse_fountain

IDS = [
    "plot.knowledge_order.v1",
    "plot.dead_acts.v1",
    "plot.two_places.v1",
    "plot.prop_provenance.v1",
]


@pytest.fixture(scope="module")
def clean(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("clean")
    write_show(build(3), d)
    return d


def stack(src: Path, out: Path, seed: int, k: int = 3) -> list[Label]:
    labels: list[Label] = []
    cur = src
    for i, name in enumerate(IDS):
        nxt = out / f"stage{i}"
        labels += get(name).inject(cur, nxt, seed, k=k)
        cur = nxt
    return labels


def final(out: Path) -> Path:
    return out / f"stage{len(IDS) - 1}"


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_planted_lines_are_exactly_the_violations(tmp_path: Path, clean: Path, seed: int) -> None:
    labels = stack(clean, tmp_path, seed)
    assert len(labels) == 12
    got = violations(read_show(final(tmp_path)))
    assert len(got) == 12
    # every violation is on the labelled line of exactly one label of its check
    for check, ep, scene, seq in got:
        owner = [
            lb
            for lb in labels
            if lb.check == check and lb.episode == ep and f"{ep}/sc/{scene}" in lb.target.refs
        ]
        assert len(owner) == 1, (check, ep, scene)
        assert line_ref(ep, scene, seq) in owner[0].target.refs


def test_labels_load_and_are_script_level(tmp_path: Path, clean: Path) -> None:
    labels = stack(clean, tmp_path, 1)
    write_labels(labels, tmp_path / "l.jsonl")
    assert load_labels(tmp_path / "l.jsonl") == labels
    assert all(lb.target.frames is None and lb.target.kind == "script_line" for lb in labels)
    assert {lb.check for lb in labels} == {
        "plot.knowledge_order",
        "plot.dead_acts",
        "plot.two_places",
        "plot.prop_provenance",
    }
    assert len({lb.label_id for lb in labels}) == 12


def test_injected_scripts_parse_and_the_line_is_where_the_label_says(
    tmp_path: Path, clean: Path
) -> None:
    labels = stack(clean, tmp_path, 2)
    out = final(tmp_path)
    show = read_show(out)
    for lb in labels:
        ep, rest = lb.target.refs[0].split("/line/")
        scene_no, seq = rest.split(".")
        parsed = parse_fountain((out / f"{ep}.fountain").read_bytes()).data
        assert parsed
        sc = next(s for s in parsed.scenes if s.number == scene_no)
        truth_line = next(s for s in show.episodes[ep] if s.no == scene_no).lines[int(seq) - 1]
        assert sc.elements[int(seq) - 1].text == truth_line.text
        assert truth_line.facts  # the planted line has truth facts for oracle runs
    assert len(set(show.touched)) == len(show.touched) == 12  # one scene each, none reused


def test_deterministic_and_seeds_differ(tmp_path: Path, clean: Path) -> None:
    a, b = stack(clean, tmp_path / "a", 5), stack(clean, tmp_path / "b", 5)
    assert a == b
    ta = (final(tmp_path / "a") / "truth.json").read_bytes()
    assert ta == (final(tmp_path / "b") / "truth.json").read_bytes()
    assert [lb.target.refs for lb in stack(clean, tmp_path / "c", 6)] != [
        lb.target.refs for lb in a
    ]


def test_dead_character_may_speak_in_a_flashback_but_never_is_planted_there(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    show = build(1)
    write_show(show, src)
    assert violations(show) == []  # the flashbacks that show the dead are not violations
    labels = get("plot.dead_acts.v1").inject(src, tmp_path / "o", 1, k=6)
    flash = {
        f"{ep}/sc/{sc.no}" for ep, scenes in show.episodes.items() for sc in scenes if sc.marker
    }
    assert labels and not flash & {r for lb in labels for r in lb.target.refs}


def _flag(lb: Label, ref: str) -> Flag:
    return Flag.model_validate(
        {
            "run_id": "r",
            "episode": lb.episode,
            "agent": "script_critic",
            "check": lb.check,
            "category": "plot_hole",
            "lang": None,
            "severity": 3,
            "confidence": 0.9,
            "tier": "must_review",
            "title": "t",
            "explanation": "e",
            "evidence": [{"kind": "script_line", "ref": ref, "role": "claim"}],
            "produced_by": {"model_variant": None, "plan_id": "p"},
            "verification": {},
        }
    )


def test_a_hand_made_flag_matches_each_planted_line(tmp_path: Path, clean: Path) -> None:
    labels = stack(clean, tmp_path, 1)
    flags = [_flag(lb, lb.target.refs[0]) for lb in labels]
    assert len(match(flags, labels)) == 12
    assert match([_flag(labels[0], "S01E06/line/1.1")], labels) == []  # a line elsewhere
