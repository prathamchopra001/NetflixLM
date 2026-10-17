"""Clearance matching: normalization, the five registry statuses, scope, strictest-status-wins."""

import pytest

from nip.agents.clearance.matching import Item, Registry, in_scope, match, normalize

LOG = (
    Item(1, "(212) 555-0234", "phone", "pending"),
    Item(2, "(415) 555-2671", "phone", "cleared"),
    Item(3, "https://velthorn.io", "url", "denied"),
    Item(4, "ines.valdor@quillmere-books.com", "email", "pending"),
    Item(5, "1428 Marrow Hollow Road", "address", "cleared"),
    Item(6, "7KLM482", "plate", "denied"),
    Item(7, "Veltrix Cola", "brand", "pending"),
    Item(8, "Acme Hardware", "logo", "pending", scope="S01E03"),
    Item(9, "Orbitel Mobile", "brand", "cleared", scope="S01E01-S01E08"),
)
REG = Registry(LOG, fictional=("Kappa Cola", "The Land of the Gatekeepers"))


def status(check: str, text: str, ep: str = "S01E01") -> tuple[str, int | None]:
    m = match(REG, check, text, ep)
    return m.status, m.item.id if m.item else None


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("clr.phone", ("(212) 555-0234", "212.555.0234")),
        ("clr.phone", ("(212) 555-0234", "+1 212 555 0234")),
        ("clr.url", ("https://velthorn.io", "www.Velthorn.io/")),
        ("clr.email", ("Hello@Velthorn.IO", "hello@velthorn.io.")),
        ("clr.plate", ("7KLM482", "7KLM-482")),
        ("clr.address", ("1428 Marrow Hollow Rd.", "1428 marrow hollow road")),
        ("clr.brand_text", ("The Veltrix Cola Co", "veltrix cola")),
    ],
)
def test_normalize_makes_variants_equal(a: str, b: tuple[str, str]) -> None:
    assert normalize(a, b[0]) == normalize(a, b[1])


def test_each_status() -> None:
    assert status("clr.brand_text", "Kappa Cola") == ("fictional", None)  # dropped
    assert status("clr.phone", "(415) 555-2671") == ("cleared", 2)
    assert status("clr.phone", "(212) 555-0234") == ("pending", 1)
    assert status("clr.url", "velthorn.io") == ("denied", 3)
    assert status("clr.phone", "(617) 482-9154") == ("unknown", None)


def test_variants_and_ocr_slips_match_names() -> None:
    assert status("clr.brand_text", "VELTRIX COLA") == ("pending", 7)
    assert status("clr.brand_text", "Veltrix Colo") == ("pending", 7)  # one OCR slip
    assert status("clr.address", "1428 Marrow Hollow Rd") == ("cleared", 5)
    assert status("clr.address", "Marrow Hollow Road") == ("cleared", 5)  # tokens contained
    assert status("clr.brand_text", "Veltrix") == ("unknown", None)  # one token is not a name


def test_identifiers_match_exactly() -> None:
    """One digit or letter off is another number or plate; a wrong 'cleared' would hide it."""
    assert status("clr.phone", "(212) 555-0235") == ("unknown", None)
    assert status("clr.plate", "7KLM462") == ("unknown", None)
    assert status("clr.email", "ines.valdor@quillmere-book.com") == ("unknown", None)


def test_a_check_only_matches_its_kinds() -> None:
    assert status("clr.url", "(212) 555-0234") == ("unknown", None)
    assert status("clr.brand_text", "Acme Hardware", "S01E03") == ("pending", 8)  # kind logo


def test_scope() -> None:
    assert status("clr.brand_text", "Acme Hardware", "S01E03") == ("pending", 8)
    assert status("clr.brand_text", "Acme Hardware", "S01E04") == ("unknown", None)
    assert status("clr.brand_text", "Orbitel Mobile", "S01E08") == ("cleared", 9)
    assert status("clr.brand_text", "Orbitel Mobile", "S01E09") == ("unknown", None)
    assert in_scope(None, "S02E01") and in_scope("", "S02E01")
    assert in_scope("S01E01, S02E05-S02E07", "S02E06") and not in_scope("S01E01", "S01E02")


def test_strictest_status_wins() -> None:
    reg = Registry(
        (
            Item(1, "Veltrix Cola", "brand", "cleared"),
            Item(2, "Veltrix Cola", "logo", "denied"),
            Item(3, "Veltrix Cola", "product", "pending"),
        )
    )
    m = match(reg, "clr.brand_text", "Veltrix Cola", "S01E01")
    assert (m.status, m.item and m.item.id) == ("denied", 2)
