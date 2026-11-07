"""A person's name or a credit line is no brand or address: GLiNER's organization / product reading
of text it also reads as a person or a job title is dropped (2.7, end credits of Sintel)."""

import pytest

from nip.agents.clearance.ocr_text import Detection, TextScanner
from nip.runtime.clients.ner import Entity, StubNER


def det(text: str) -> Detection:
    return Detection(0, 0, text, (0.1, 0.2, 0.3, 0.05), 0.95, "pp-ocrv6-medium")


def ent(text: str, label: str, score: float) -> Entity:
    return Entity(text=text, label=label, start=0, end=len(text), score=score)


@pytest.fixture(scope="module")
def scanner() -> TextScanner:
    recorded = {
        "Ton Roosendaal": [ent("Ton Roosendaal", "product", 0.8),
                           ent("Ton Roosendaal", "person", 0.9)],
        "CHARACTER RIGGING": [ent("CHARACTER RIGGING", "product", 0.86),
                              ent("CHARACTER RIGGING", "job title", 0.7)],
        "Dell Computers": [ent("Dell Computers", "organization", 0.9)],
        "Maybe Person": [ent("Maybe Person", "organization", 0.8),
                         ent("Maybe Person", "person", 0.4)],
    }  # fmt: skip
    return TextScanner(StubNER(recorded))


@pytest.mark.parametrize(
    ("text", "expect"),
    [
        ("Ton Roosendaal", []),  # also a person
        ("CHARACTER RIGGING", []),  # also a job title
        ("Dell Computers", ["clr.brand_text"]),  # only an organization
        (
            "Maybe Person",
            ["clr.brand_text"],
        ),  # a person reading below person_min_score does not count
    ],
)
def test_names_and_credits_are_not_brands(
    scanner: TextScanner, text: str, expect: list[str]
) -> None:
    assert [c.check for c in scanner.candidates([det(text)])] == expect


def lines(texts: list[str]) -> list[Detection]:
    return [det(t) for t in texts]


def test_a_credits_card_gives_no_gliner_guesses_but_keeps_the_deny_lists_and_identifiers() -> None:
    recorded = {"Dell Computers": [ent("Dell Computers", "organization", 0.9)]}
    scanner = TextScanner(
        StubNER(recorded), deny_brands=["Orbitel Mobile"], deny_addresses=["77 Saltwick Lane"]
    )
    filler = [f"CREDIT LINE {i}" for i in range(6)]
    sparse = lines(["Dell Computers"])
    card = lines(
        ["Dell Computers", "Orbitel Mobile", "77 Saltwick Lane", "(617) 482-9154", *filler]
    )
    assert [c.check for c in scanner.candidates(sparse)] == ["clr.brand_text"]
    got = sorted((c.check, c.text) for c in scanner.candidates(card))
    assert got == [  # no GLiNER brand for "Dell Computers" on the card
        ("clr.address", "77 Saltwick Lane"),
        ("clr.brand_text", "Orbitel Mobile"),
        ("clr.phone", "(617) 482-9154"),
    ]
    assert len(card) == 10 >= 8 and len(sparse) < 8


def test_logged_items_survive_the_junk_rules_but_unlogged_look_alikes_do_not() -> None:
    """N1: credit words, person/role overlaps and the film's own names drop only what no clearance
    log entry (a deny list) found."""
    recorded = {
        "SOUND DESIGN": [
            ent("SOUND DESIGN", "product", 0.8),
            ent("SOUND DESIGN", "job title", 0.9),
        ],
        "Studio Camera Set": [ent("Studio Camera Set", "address", 0.8)],
    }
    logged = TextScanner(
        StubNER(recorded),
        deny_brands=["Sound Design", "Waffle House"],
        deny_addresses=["Studio Camera Set"],
        fictional=["House"],  # the show's own title
    )
    got = sorted((c.check, c.text) for c in logged.candidates(
        lines(["SOUND DESIGN", "Studio Camera Set", "WAFFLE HOUSE"])))  # fmt: skip
    assert got == [
        ("clr.address", "Studio Camera Set"),
        ("clr.brand_text", "SOUND DESIGN"),
        ("clr.brand_text", "WAFFLE HOUSE"),
    ]
    unlogged = TextScanner(StubNER(recorded), fictional=["House"])
    assert unlogged.candidates(lines(["SOUND DESIGN", "Studio Camera Set", "WAFFLE HOUSE"])) == []
