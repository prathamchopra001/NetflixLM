"""Grounding validator: normalized quote vs the cited line (D-005)."""

from nip.knowledge.grounding import grounded, normalize, score

LINE = "So it is true. Ada Kovac is the informant. All this time."


def test_normalize_unifies_marks_and_whitespace() -> None:
    assert normalize("  “It’s here” —\n now ") == '"It\'s here" - now'


def test_exact_and_typographic_quotes_pass() -> None:
    assert score("Ada Kovac is the informant", LINE) == 100
    assert grounded("Ada Kovac’s the informant".replace("’s", " is"), LINE)
    assert grounded("It’s late", "It's late, Maya.")


def test_fabricated_quote_is_dropped() -> None:
    assert not grounded("Leo Park is the informant", LINE)
    assert not grounded("Ada hides the brass ledger in the safe", LINE)
    assert not grounded("", LINE)


def test_a_quote_longer_than_its_line_needs_the_whole_quote() -> None:
    padded = LINE + " She also stole the tide map from the archive."
    assert score(LINE, LINE) == 100 and not grounded(padded, LINE)


def test_threshold_is_a_parameter() -> None:
    q = "Ada Kovak is the informant"  # one wrong letter
    assert grounded(q, LINE, 85) and not grounded(q, LINE, 99)
