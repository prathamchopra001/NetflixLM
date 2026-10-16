import importlib.util
from pathlib import Path

from nip.ingest import parse, parse_fdx, parse_fountain, parse_pdf

FIXTURES = Path(__file__).parents[2] / "fixtures" / "ingest"


def _summary(script):
    return [
        (s.number, s.heading, [(e.kind, e.speaker, e.text) for e in s.elements])
        for s in script.scenes
    ]


def test_fountain_fixture():
    r = parse_fountain((FIXTURES / "sample.fountain").read_bytes())
    assert r.ok and r.data.title == "Harbor Lights"
    assert _summary(r.data) == [
        (
            "12A",
            "INT. HARBOR WAREHOUSE - NIGHT",
            [
                ("action", None, "Maya enters, flashlight sweeping the crates."),
                ("parenthetical", "MAYA", "whispering"),
                ("dialogue", "MAYA", "Where is he?\nHe said nine o'clock."),  # *emphasis* stripped
                ("dialogue", "LEO", "Behind you."),  # dual dialogue
                ("transition", None, "CUT TO:"),  # boneyard before it removed
            ],
        ),
        ("2", "FLASHBACK - 1998", [("action", None, "Rain on a window.")]),
        ("3", "EXT. DOCK - DAY", [("dialogue", "McCoy", "Morning.")]),
    ]
    assert [s.time_of_day for s in r.data.scenes] == ["NIGHT", None, "DAY"]
    assert r.warnings == ["1 element(s) before the first scene heading were ignored"]  # FADE IN:


def test_fountain_cp1252_bytes():
    r = parse_fountain("INT. CAFÉ - DAY\n\nJOSÉ\nHola.\n".encode("cp1252"))
    assert r.data.scenes[0].heading == "INT. CAFÉ - DAY"
    assert r.data.scenes[0].elements[0].speaker == "JOSÉ"


def test_no_scene_headings_rejected():
    r = parse_fountain("Title: x\n\nJust some prose with no headings.\n")
    assert not r.ok and r.data is None
    assert r.errors[0].reason == "Script has no scene headings"
    assert r.rejection("Script failed to parse")["error"]["code"] == "INPUT_REJECTED"


def test_duplicate_scene_number_warns():
    r = parse_fountain("INT. A - DAY #1#\n\nx\n\nINT. B - DAY #1#\n\ny\n")
    assert r.ok and r.warnings == ["Duplicate scene number 1"]


def test_fdx_fixture_keeps_every_text_run():
    r = parse_fdx((FIXTURES / "sample.fdx").read_bytes())
    assert r.ok
    assert _summary(r.data) == [
        (
            "12A",
            "INT. HARBOR WAREHOUSE - NIGHT",
            [
                # the first <Text> run alone would give 'Maya enters, ' (screenplay-tools' bug)
                ("action", None, "Maya enters, flashlight sweeping the crates."),
                ("parenthetical", "MAYA", "whispering"),
                ("dialogue", "MAYA", "Where is he?"),
                ("dialogue", "LEO", "Behind you."),  # inside <DualDialogue>
                ("transition", None, "CUT TO:"),
            ],
        ),
        ("2", "EXT. DOCK - DAY", [("action", None, "Gulls wheel.")]),
    ]


def test_fdx_malformed_and_wrong_root():
    r = parse_fdx("<FinalDraft>\n<Content>\n<Paragraph></Content></FinalDraft>")
    assert not r.ok and r.errors[0].line == 3
    r = parse_fdx("<html/>")
    assert not r.ok and "FinalDraft" in r.errors[0].reason


def test_pdf_fixture():
    r = parse_pdf((FIXTURES / "screenplay.pdf").read_bytes())
    assert r.ok
    assert _summary(r.data) == [
        (
            "1",
            "INT. HARBOR WAREHOUSE - NIGHT",
            [
                ("action", None, "Maya enters, flashlight sweeping the crates."),
                ("parenthetical", "MAYA", "whispering"),
                ("dialogue", "MAYA", "Where is he? He said nine o'clock."),  # wrapped lines joined
                ("dialogue", "LEO", "Behind you."),  # (O.S.) dropped from the speaker
                ("transition", None, "CUT TO:"),
            ],
        ),
        (
            "2",
            "EXT. DOCK - DAY",
            [
                ("action", None, "Gulls wheel over the water."),  # page number '2.' skipped
                ("dialogue", "MAYA", "That's the boat."),
                ("dialogue", "MAYA", "Come on."),  # (CONT'D) dropped
            ],
        ),
        (
            "3",
            "INT. SAFEHOUSE - CONTINUOUS",
            [("action", None, "Ada waits by the window."), ("transition", None, "FADE OUT.")],
        ),
    ]


def _pdf_builder():
    spec = importlib.util.spec_from_file_location("mk", FIXTURES / "make_screenplay_pdf.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build


def test_pdf_without_text_and_garbage_rejected():
    r = parse_pdf(_pdf_builder()([[]]))
    assert not r.ok and "no extractable text" in r.errors[0].reason
    r = parse_pdf(b"not a pdf")
    assert not r.ok and r.errors[0].reason.startswith("Unreadable PDF")


def test_pdf_numbered_headings_and_no_heading():
    build = _pdf_builder()
    r = parse_pdf(build([[(108, "12 INT. HOUSE - DAY 12"), (108, "Action.")]]))
    assert r.data.scenes[0].number == "12" and r.data.scenes[0].heading == "INT. HOUSE - DAY"
    assert not parse_pdf(build([[(108, "Just prose.")]])).ok


def test_dispatch():
    assert parse("fountain", (FIXTURES / "sample.fountain").read_bytes()).ok
    assert parse("fdx", (FIXTURES / "sample.fdx").read_bytes()).ok
