"""The character cue's extension survives ingest beside the clean speaker name (2.1B re-review N3):
derived presence reads it, entity resolution does not."""

from pathlib import Path

from nip.ingest import parse_fdx, parse_fountain, parse_pdf
from nip.ingest.script import cue_extension, speaker_name
from nip.knowledge.extract import OFFSCREEN

FIXTURES = Path(__file__).parents[2] / "fixtures" / "ingest"


def _cues(script) -> list[tuple[str | None, str | None]]:  # type: ignore[no-untyped-def]
    return [(e.speaker, e.extension) for s in script.scenes for e in s.elements if e.speaker]


def test_fountain_fdx_and_pdf_keep_the_extension_and_a_clean_speaker() -> None:
    fountain = _cues(parse_fountain((FIXTURES / "sample.fountain").read_bytes()).data)
    assert ("MAYA", "(V.O.)") in fountain and ("LEO", None) in fountain
    fdx = _cues(parse_fdx((FIXTURES / "sample.fdx").read_bytes()).data)
    assert ("MAYA", "(V.O.)") in fdx
    pdf = _cues(parse_pdf((FIXTURES / "screenplay.pdf").read_bytes()).data)
    assert ("LEO", "(O.S.)") in pdf and ("MAYA", "(CONT'D)") in pdf


def test_cue_parts_and_which_extensions_are_off_screen() -> None:
    assert speaker_name("MAYA (V.O.) (CONT'D)") == "MAYA" and speaker_name("MAYA") == "MAYA"
    assert cue_extension("MAYA (V.O.) (CONT'D)") == "(V.O.) (CONT'D)"
    assert cue_extension("MAYA") is None
    for cue in ("MAYA (V.O.)", "LEO (O.S.)", "DOV (O.C.)", "ADA (ON PHONE)", "RUI (FILTERED)",
                "INES (PRE-LAP)"):  # fmt: skip
        assert OFFSCREEN.search(cue), cue
    for cue in ("MAYA (CONT'D)", "MAYA", "DOC", "ROSS"):  # CONT'D is still in the room
        assert not OFFSCREEN.search(cue), cue
