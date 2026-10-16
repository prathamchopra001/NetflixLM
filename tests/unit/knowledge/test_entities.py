"""Name matching of entity resolution: whole words only (review I-1), both directions."""

from nip.knowledge.entities import RESOLVE_THRESHOLD, Resolver, score


def resolver(names: dict[str, int]) -> Resolver:
    r = object.__new__(Resolver)  # the matching part only: no database
    r.names, r.ids = list(names), list(names.values())
    return r


NAMES = {
    "Ada Kovac": 1,
    "Addie": 1,
    "Tomas Vale": 2,
    "Tom": 2,
    "Dov Lindqvist": 3,
    "Dov": 3,
    "Rui Marlow": 4,
    "Harbor Warehouse": 5,
    "Harbor City PD": 6,
    "Harbor Lights": 7,
    "the informant": 1,
}


def test_a_shortened_name_resolves() -> None:
    r = resolver(NAMES)
    assert [r.match(n) for n in ("Ada", "kovac", "TOMAS", "Tomas Vale", "informant")] == [
        1,
        1,
        2,
        2,
        1,
    ]
    assert r.match("Tomas Vael") == 2  # a spelling slip: ratio 90


def test_containment_inside_a_longer_word_or_name_does_not_resolve() -> None:
    for name in ("tomato", "Dover Street", "Ruins", "Dov Street", "Captain Ada Kovac"):
        assert resolver(NAMES).match(name) is None, name


def test_ambiguous_or_empty_names_do_not_resolve() -> None:
    assert resolver(NAMES).match("Harbor") is None  # warehouse or lights
    assert resolver(NAMES).match("!!") is None


def test_scores() -> None:
    assert score("Ada", "Ada Kovac") == 100 and score("tomato", "Tom") < RESOLVE_THRESHOLD
    assert score("Dover Street", "Dov") < RESOLVE_THRESHOLD
    assert score("Tomas", "Tomas Vale takes money from Greywater Holdings") < RESOLVE_THRESHOLD
    assert score("Marrow Street", "Marrow Street Garage") == 100
