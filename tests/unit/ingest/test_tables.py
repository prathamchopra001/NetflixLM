from pathlib import Path

from nip.ingest import ClearanceEntry, GlossaryEntry, parse, parse_clearance_log, parse_glossary

FIXTURES = Path(__file__).parents[2] / "fixtures" / "ingest"


def test_glossary_fixture():
    r = parse_glossary((FIXTURES / "glossary.csv").read_bytes())
    assert r.ok and r.warnings == []
    assert r.data[1] == GlossaryEntry("the Hollow", "es-419", "el Hueco", "")
    assert len(r.data) == 3


def test_clearance_fixture():
    r = parse_clearance_log((FIXTURES / "clearance_log.csv").read_bytes())
    assert r.ok and r.warnings == []
    assert r.data[0] == ClearanceEntry(
        "Acme Hardware", "logo", "pending", "S01E03", "Storefront in ep 3 - legal reviewing"
    )
    assert r.data[1].scope == ""


def test_columns_missing_is_error_unknown_is_warning():
    r = parse_clearance_log("item,status\nAcme,cleared\n")
    assert not r.ok and r.data is None
    assert [(e.reason, e.line) for e in r.errors] == [("Missing required column 'kind'", 1)]
    r = parse_glossary("term,lang,approved_rendering,extra\nWren,es,Wren,x\n")
    assert r.ok and r.warnings == ["Unknown column 'extra'"]
    r = parse_glossary("")
    assert not r.ok and r.errors[0].reason == "File is empty"


def test_optional_columns_may_be_absent_and_bom_and_header_case():
    r = parse_glossary("﻿Term,Lang,Approved_Rendering\nWren,es,Wren\n")
    assert r.ok and r.data == [GlossaryEntry("Wren", "es", "Wren", "")]


def test_row_errors_carry_line_numbers():
    r = parse_clearance_log("item,kind,status\nA,logo,cleared\nB,logo,maybe\n,logo,pending\n")
    assert [e.line for e in r.errors] == [3, 4]
    assert "maybe" in r.errors[0].reason and r.errors[1].reason == "Empty 'item'"
    r = parse_glossary("term,lang,approved_rendering\nWren,es_419,Wren\nx,en,\n")
    assert [(e.line, e.reason) for e in r.errors] == [
        (2, "Invalid language tag 'es_419'"),
        (3, "Empty 'approved_rendering'"),
    ]
    assert parse_glossary("term,lang,approved_rendering\na,en,b,c\n").errors[0].line == 2


def test_status_case_and_duplicates_warn_and_blank_rows_skipped():
    r = parse_clearance_log("item,kind,status\nA,logo,CLEARED\n\nA,logo,pending\n")
    assert r.ok and [c.status for c in r.data] == ["cleared", "pending"]
    assert r.warnings == ["line 4: duplicate entry for 'A' (scope '')"]
    r = parse_glossary("term,lang,approved_rendering\nx,es,a\nx,es,b\nx,fr,c\n")
    assert r.ok and r.warnings == ["line 3: 'x' (es) has conflicting approved renderings"]


def test_dispatch_by_kind():
    assert parse("csv", (FIXTURES / "glossary.csv").read_bytes(), "glossary").data[0].term == "Wren"
    assert parse("csv", (FIXTURES / "clearance_log.csv").read_bytes(), "clearance_log").ok
