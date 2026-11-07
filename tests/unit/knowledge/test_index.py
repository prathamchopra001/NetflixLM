"""Scene text for the index and the text embedder backends (no database, no model)."""

import math

import pytest

from nip.knowledge.index import scene_text
from nip.runtime.catalog import load_catalog
from nip.runtime.clients.text_embedder import EMBED_DIM, HashEmbedder, make_embedder


def cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_scene_text_has_heading_action_and_speakers_but_no_transitions() -> None:
    lines = [
        ("action", None, "Maya enters."),
        ("dialogue", "MAYA", "Hello there."),
        ("parenthetical", "MAYA", "quietly"),
        ("transition", None, "CUT TO:"),
    ]
    assert scene_text("INT. ROOM - DAY", lines) == (
        "INT. ROOM - DAY\nMaya enters.\nMAYA: Hello there.\n(quietly)"
    )
    assert scene_text("EXT. DOCK - NIGHT", []) == "EXT. DOCK - NIGHT"


def test_hash_embedder_is_deterministic_unit_length_and_lexical() -> None:
    e = HashEmbedder()
    a, b, c = e.embed(["the rusted key opens the door", "a rusted key", "tomorrow it rains"])
    assert e.embed(["a rusted key"]) == [b]
    assert len(a) == EMBED_DIM and math.isclose(cos(a, a), 1.0, abs_tol=1e-9)
    assert cos(a, b) > 0.3 > abs(cos(a, c))
    assert e.embed([""]) == [[0.0] * EMBED_DIM]  # no words: the zero vector, not a crash


def test_make_embedder_uses_the_stub_for_the_stub_variant() -> None:
    assert isinstance(make_embedder("stub", load_catalog()), HashEmbedder)
    with pytest.raises(KeyError):  # an unknown variant with no catalog repo: no silent fallback
        make_embedder("no-such-embedder")
