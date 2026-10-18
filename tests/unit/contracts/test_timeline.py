import pytest

from nip.contracts import refs
from nip.contracts.flag import EvidenceKind
from nip.contracts.timeline import Span, Timeline


def _cue(i: int) -> Span:
    return Span(kind=EvidenceKind.SUBTITLE_CUE, ref=refs.cue("E1", "es", i), lang="es")


def test_refs_build_and_parse() -> None:
    assert refs.parse(refs.scene("S01E03", "12A")) == ("scene", "S01E03", "12A", None)
    assert refs.parse(refs.shot("S01E03", 118)) == ("shot", "S01E03", "118", None)
    assert refs.parse(refs.keyframe("S01E03", 118, 0)) == ("keyframe", "S01E03", "118.0", None)
    assert refs.parse(refs.cue("S01E03", "es-419", 212)) == (
        "subtitle_cue",
        "S01E03",
        "212",
        "es-419",
    )
    assert refs.parse("S01E03/line/12.4").kind is EvidenceKind.SCRIPT_LINE
    assert refs.parse("fact/8812") == ("fact", None, "8812", None)
    assert refs.parse("clr/77").kind is EvidenceKind.CLEARANCE_ITEM


def test_occurrence_refs() -> None:
    ref = refs.occurrence("3fa9c0d1e2b4")
    assert ref == "clr/occ-3fa9c0d1e2b4" and refs.is_occurrence(ref)
    assert refs.parse(ref) == ("clearance_item", None, "occ-3fa9c0d1e2b4", None)
    assert not refs.is_occurrence("clr/77") and not refs.is_occurrence("S01E01/kf/1.0")


@pytest.mark.parametrize("bad", ["sintel_en.srt", "E1/es/x", "E1//3", "fact/", "E1/sc/1/2", "x/7"])
def test_refs_parse_rejects(bad: str) -> None:
    with pytest.raises(ValueError, match="not an evidence ref"):
        refs.parse(bad)


def test_copy_resolves_its_own_spans() -> None:
    tl = Timeline(episode="E1", fps=(24, 1), duration_frames=10, spans=[_cue(1)])
    assert tl.resolve("E1/es/1") is not None
    copy = tl.model_copy(update={"spans": (_cue(2),)})
    assert copy.resolve("E1/es/2") is not None and copy.resolve("E1/es/1") is None
    assert tl.resolve("E1/es/1") is not None and tl.resolve("E1/es/2") is None
    with pytest.raises(ValueError, match="duplicate timeline refs"):
        tl.model_copy(update={"spans": (_cue(1), _cue(1))}).resolve("E1/es/1")


def test_spans_cannot_be_appended_to() -> None:
    tl = Timeline(episode="E1", fps=(24, 1), duration_frames=10, spans=[_cue(1)])
    assert isinstance(tl.spans, tuple)
    with pytest.raises(AttributeError):
        tl.spans.append(_cue(2))  # type: ignore[attr-defined]
