"""The synthetic show: deterministic, parses through nip.ingest, truth matches the scripts."""

import re
from pathlib import Path

import pytest

from eval.synthetic import build, read_show, write_show
from eval.synthetic.model import line_ref, setups, truth
from eval.synthetic.rules import violations
from nip.contracts import refs
from nip.ingest import parse_bible, parse_fountain


@pytest.fixture(scope="module")
def show_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("show")
    write_show(build(1), d)
    return d


def test_shape(show_dir: Path) -> None:
    show = read_show(show_dir)
    assert list(show.episodes) == [f"S01E0{i}" for i in range(1, 7)]
    assert all(len(sc) == 25 for sc in show.episodes.values())


def test_same_seed_is_byte_identical_and_other_seeds_differ(tmp_path: Path, show_dir: Path) -> None:
    write_show(build(1), tmp_path / "again")
    names = sorted(p.name for p in show_dir.iterdir())
    assert names == sorted(p.name for p in (tmp_path / "again").iterdir())
    assert all((show_dir / n).read_bytes() == (tmp_path / "again" / n).read_bytes() for n in names)
    write_show(build(2), tmp_path / "other")
    assert (show_dir / "truth.json").read_bytes() != (
        tmp_path / "other" / "truth.json"
    ).read_bytes()


def test_every_script_and_the_bible_pass_the_ingest_door(show_dir: Path) -> None:
    for f in sorted(show_dir.glob("*.fountain")):
        p = parse_fountain(f.read_bytes())
        assert p.ok and p.data and not p.warnings, (f, p.errors, p.warnings)
    b = parse_bible((show_dir / "bible.yaml").read_bytes())
    assert b.ok and b.data and not b.warnings, (b.errors, b.warnings)
    assert {c.id for c in b.data.characters} == {
        e.id for e in read_show(show_dir).entities if e.kind == "character"
    }


def test_truth_lines_are_the_parsed_script_elements_in_order(show_dir: Path) -> None:
    show = read_show(show_dir)
    for ep, scenes in show.episodes.items():
        parsed = parse_fountain((show_dir / f"{ep}.fountain").read_bytes()).data
        assert parsed and len(parsed.scenes) == len(scenes)
        for ps, sc in zip(parsed.scenes, scenes, strict=True):
            assert ps.number == sc.no and ps.heading == sc.heading
            assert [(e.kind, e.text) for e in ps.elements] == [
                (ln.kind, ln.text) for ln in sc.lines
            ]
            for e, ln in zip(ps.elements, sc.lines, strict=True):
                if ln.speaker:
                    assert e.speaker == show.entity(ln.speaker).name.split()[0].upper()


def test_quotes_and_mentions_are_in_their_lines(show_dir: Path) -> None:
    show = read_show(show_dir)
    n_facts = n_mentions = 0
    for scenes in show.episodes.values():
        for sc in scenes:
            for ln in sc.lines:
                for f in ln.facts:
                    assert f.quote in ln.text
                    n_facts += 1
                for m in ln.mentions:
                    assert m.surface in ln.text
                    ent = show.entity(m.entity)
                    known = {ent.name, ent.name.split()[0], *(a for a, _ in ent.aliases)}
                    assert m.surface in known
                    n_mentions += 1
    assert n_facts > 300 and n_mentions > 200


def test_mentions_cover_names_nicknames_and_descriptions(show_dir: Path) -> None:
    show = read_show(show_dir)
    kinds = {
        m.kind
        for scenes in show.episodes.values()
        for sc in scenes
        for ln in sc.lines
        for m in ln.mentions
    }
    assert kinds == {"name", "nickname", "description"}


def test_arc_structure(show_dir: Path) -> None:
    show = read_show(show_dir)
    flat = [sc for scenes in show.episodes.values() for sc in scenes]
    assert sum(sc.marker == "flashback" for sc in flat) == 2
    assert sum(sc.marker == "same_time" for sc in flat) == 6  # one INTERCUT pair per episode
    for scenes in show.episodes.values():
        i = next(i for i, sc in enumerate(scenes) if sc.marker == "same_time")
        a, b = scenes[i - 1], scenes[i]
        assert a.story_seq == b.story_seq and a.location != b.location
        assert not show.cast(a) & show.cast(b)
    # flashbacks come first in story order and are listed as bible overrides
    assert min(sc.story_seq for sc in flat if sc.marker != "flashback") > max(
        sc.story_seq for sc in flat if sc.marker == "flashback"
    )
    bible = parse_bible((show_dir / "bible.yaml").read_bytes()).data
    assert bible and len(bible.story_overrides) == 2 and len(bible.secrets) == 4
    pairs = setups(show)
    assert len(pairs) == 3 and all(p["setup"] != p["payoff"] for p in pairs)


def test_clean_show_breaks_no_layer1_rule() -> None:
    for seed in range(1, 21):
        assert violations(build(seed)) == [], seed


def test_truth_json_carries_refs_and_loads_back(show_dir: Path) -> None:
    t = truth(read_show(show_dir))
    sc = t["episodes"]["S01E02"][3]
    assert sc["ref"] == refs.scene("S01E02", sc["no"])
    assert sc["lines"][1]["ref"] == line_ref("S01E02", sc["no"], 2)
    assert read_show(show_dir).model_dump() == read_show(show_dir / "truth.json").model_dump()


def test_every_entity_surface_in_a_line_has_a_mention_record(
    show_dir: Path, tmp_path: Path
) -> None:
    """EXP-020 scores resolution against these records, so none may be missing: characters (name,
    nickname, description), locations, props, orgs and brands, in the clean and injected show."""
    from eval.injectors import get

    out = tmp_path / "inj"
    get("plot.knowledge_order.v1").inject(show_dir, out, 1, k=3)
    kinds = set()
    for d in (show_dir, out):
        show = read_show(d)
        surfaces: dict[str, set[str]] = {}  # surface -> entity ids that own it
        for e in show.entities:
            if e.kind == "character":
                names = {e.name, e.name.split()[0], *(a for a, _ in e.aliases)}
            elif e.kind in ("location", "prop", "org", "brand"):
                names = {e.name}
            else:
                continue
            for n in names:
                surfaces.setdefault(n, set()).add(e.id)
        for scenes in show.episodes.values():
            for sc in scenes:
                for ln in sc.lines:
                    have = {(m.surface, m.entity) for m in ln.mentions}
                    for surface, owners in surfaces.items():
                        n_text = len(
                            re.findall(f"(?<![A-Za-z]){re.escape(surface)}(?![A-Za-z])", ln.text)
                        )
                        if not n_text:
                            continue
                        # a surface inside a longer recorded one ("Ada" in "Ada Kovac") is fine
                        inside = any(
                            surface in m.surface and surface != m.surface for m in ln.mentions
                        )
                        assert inside or any((surface, o) in have for o in owners), (
                            ln.text,
                            surface,
                        )
                    kinds |= {show.entity(m.entity).kind for m in ln.mentions}
    assert kinds == {"character", "location", "prop", "org", "brand"}
    informant = [
        m
        for scenes in read_show(show_dir).episodes.values()
        for sc in scenes
        for ln in sc.lines
        for m in ln.mentions
        if m.surface == "the informant"
    ]
    assert informant and all(m.entity == "ada" and m.kind == "description" for m in informant)
