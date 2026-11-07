from fractions import Fraction
from pathlib import Path

from nip.ingest import parse_srt, parse_ttml, parse_vtt

FIXTURES = Path(__file__).parents[2] / "fixtures" / "ingest"


def _ttml(body: str, attrs: str = "") -> str:
    return (
        '<tt xmlns="http://www.w3.org/ns/ttml" xmlns:ttp="http://www.w3.org/ns/ttml#parameter" '
        f'xml:lang="en" {attrs}><body><div>{body}</div></body></tt>'
    )


def test_srt_fixture_crlf():
    r = parse_srt((FIXTURES / "sample.srt").read_bytes())
    assert r.ok and r.data.frame_rate is None
    assert [(c.idx, c.start_ms, c.end_ms, c.text, c.line) for c in r.data.cues] == [
        (1, 1000, 2500, "Hello there\nsecond line", 2),
        (2, 3000, 4000, "Goodbye", 7),
    ]


def test_vtt_fixture():
    r = parse_vtt((FIXTURES / "sample.vtt").read_bytes())
    assert r.ok and r.data.frame_rate is None
    assert [(c.start_ms, c.end_ms, c.text, c.line) for c in r.data.cues] == [
        (1000, 2500, "Hello there\nsecond line", 6),  # short mm:ss.mmm form, cue settings ignored
        (3000, 4000, "Goodbye", 10),
    ]


def test_srt_utf16_detected():
    raw = "1\n00:00:01,000 --> 00:00:02,000\nñandú\n".encode("utf-16")
    r = parse_srt(raw)
    assert r.ok and r.data.cues[0].text == "ñandú"


def test_srt_malformed_timing_reports_line():
    srt = "1\n00:00:01,000 --> 00:00:02,000\nok\n\n2\n00:00:03,000 -> 00:00:04,000\nbad arrow\n"
    r = parse_srt(srt)
    assert not r.ok and [e.line for e in r.errors] == [6]
    r = parse_srt("1\n00:00:01,000 00:00:02,000\ntext\n")  # no arrow at all
    assert not r.ok and r.errors[0].line == 2


def test_srt_end_before_start_empty_and_no_cues():
    r = parse_srt("1\n00:00:05,000 --> 00:00:04,000\nx\n\n2\n00:00:06,000 --> 00:00:07,000\n\n")
    assert [(e.line, "end" in e.reason) for e in r.errors] == [(2, True)]
    assert r.warnings == ["cue 2: empty text"]
    r = parse_srt("nothing here")
    assert not r.ok and r.errors[0].reason == "Subtitle file has no cues"


def test_srt_out_of_order_warns():
    r = parse_srt("1\n00:00:05,000 --> 00:00:06,000\na\n\n2\n00:00:01,000 --> 00:00:02,000\nb\n")
    assert r.ok and r.warnings == ["cue 2: starts before cue 1"]


def test_vtt_header_and_karaoke_tags():
    r = parse_vtt("00:01.000 --> 00:02.000\nx\n")
    assert not r.ok and r.errors[0].line == 1
    r = parse_vtt("WEBVTT\n\n00:01.000 --> 00:02.000\nhi <00:01.500>there\n")
    assert r.ok  # an inline timestamp tag is not a malformed cue timing


def test_ttml_fixture_frames_with_declared_rate():
    r = parse_ttml((FIXTURES / "sample.ttml").read_bytes())
    assert r.ok
    assert r.data.frame_rate == Fraction(24000, 1001)
    # 00:00:01:00 and 00:00:03:12 at 24000/1001 fps -> exactly 1.001 s and 3.5035 s
    assert [(c.start_ms, c.end_ms, c.text) for c in r.data.cues] == [
        (1001, 3504, "Hola\nmundo cursiva"),
        (6006, 8008, "Adios"),
    ]


def test_ttml_clock_times_no_declared_rate_and_div_offset():
    r = parse_ttml(_ttml('<p begin="00:00:01.500" end="00:00:02.000">a</p>'))
    assert r.ok and r.data.frame_rate is None and r.data.cues[0].start_ms == 1500
    r = parse_ttml(
        '<tt xmlns="http://www.w3.org/ns/ttml"><body><div begin="10s" end="20s">'
        '<p begin="1s" end="2s">a</p></div></body></tt>'
    )
    assert (r.data.cues[0].start_ms, r.data.cues[0].end_ms) == (11000, 12000)


def test_ttml_bad_time_is_a_validation_error():
    r = parse_ttml(_ttml('<p begin="00:00:01.000" end="00:00:xx.000">a</p>'))
    assert not r.ok
    assert any("end attribute" in e.reason for e in r.errors)  # ttconv's log, turned into an error
    assert any("missing or invalid" in e.reason for e in r.errors)


def test_ttml_malformed_xml_reports_line_and_empty():
    r = parse_ttml('<tt xmlns="http://www.w3.org/ns/ttml">\n<body>\n<p>unclosed</body></tt>')
    assert not r.ok and r.errors[0].line == 3
    r = parse_ttml(_ttml(""))
    assert not r.ok and r.errors[0].reason == "Subtitle file has no cues"


def test_ttml_cue_errors_carry_source_lines():
    ttml = (
        '<tt xmlns="http://www.w3.org/ns/ttml" xml:lang="en">\n'
        "<body>\n<div>\n"
        '<p begin="00:00:01.000" end="00:00:02.000">ok</p>\n'
        '<p begin="00:00:03.000" end="00:00:xx.000">bad time</p>\n'
        '<p begin="00:00:05.000">no end</p>\n'
        '<p begin="00:00:08.000" end="00:00:07.000">backwards</p>\n'
        "</div>\n</body>\n</tt>"
    )
    r = parse_ttml(ttml)
    by_reason = {e.reason.split(":")[0]: e.line for e in r.errors}
    assert by_reason["cue 2"] == 5 and by_reason["cue 3"] == 6
    assert by_reason["cue 4"] == 7  # end before start (from the cue check)
    assert all(e.line is not None for e in r.errors if not e.reason.startswith("ttconv"))
    assert [c.line for c in r.data.cues] == [4, 7]
    assert all(e.line is None for e in r.errors if e.reason.startswith("ttconv"))  # 2 bad cues
    one = parse_ttml(ttml.replace('<p begin="00:00:05.000">no end</p>\n', ""))
    assert [e.line for e in one.errors if e.reason.startswith("ttconv")] == [5]
