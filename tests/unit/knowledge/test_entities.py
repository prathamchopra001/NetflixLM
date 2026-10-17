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


class Minting(Resolver):
    """Candidates without a database: a new id per call, added to the names."""

    def candidate(self, name: str, kind: str) -> int:
        eid = 100 + len(self.names)
        self._add(name, eid)
        return eid


def test_an_exact_name_wins_and_a_repeated_unknown_name_reuses_its_candidate() -> None:  # N-1
    r = object.__new__(Minting)
    r.keys, r.names, r.ids = {}, [], []
    for name, eid in {
        "Tomas Vale": 2,
        "Mira Vale": 8,
        "Ada Maria Kovac": 9,
        "Ada Kovac": 1,
    }.items():
        r._add(name, eid)
    first = r.resolve("UNKNOWN", "Vale", "present_at", "subject")
    assert first >= 100 and r.resolve("UNKNOWN", "VALE", "present_at", "subject") == first
    assert r.resolve("UNKNOWN", "Ada Kovac", "present_at", "subject") == 1
    assert r.match("ada  kovac") == 1 and r.match("Ada Maria") == 9


def test_argument_kinds_must_fit_the_predicate() -> None:  # 2.1B, EXP-006 follow-up
    r = resolver(NAMES)
    r.kinds = {1: "character", 3: "character", 5: "location", 6: "org", 9: "secret"}
    assert r.typed("present_at", 1, 5) and not r.typed("present_at", 5, 1)
    assert not r.typed("holds", 3, 1)  # "holds dov -> ada": a character is not a prop
    assert r.typed("holds", 3, "thermos")  # a new name becomes a prop candidate
    assert (
        r.typed("learns", 1, 9) and not r.typed("learns", 1, 5) and not r.typed("learns", 1, None)
    )
    assert not r.typed("relationship", 1, 1) and r.typed("relationship", 1, 3)
    assert (
        r.typed("mentions", 1, 6) and r.typed("decision", 3, None) and not r.typed("state", 9, None)
    )
    assert not r.typed("present_at", None, 5)
