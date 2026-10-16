from pathlib import Path

from nip.ingest import parse, parse_bible

FIXTURES = Path(__file__).parents[2] / "fixtures" / "ingest"
MIN = "show: s\ncharacters:\n  - {id: a, name: A}\n  - {id: b, name: B}\n"


def test_fixture():
    r = parse_bible((FIXTURES / "bible.yaml").read_bytes())
    assert r.ok and r.warnings == []
    b = r.data
    assert [c.id for c in b.characters] == ["maya", "leo", "ada"]
    assert b.characters[2].identity_hidden_until == "S01E08"
    step = b.relationships[0].timeline[1]
    assert (step.from_, step.kind) == ("S01E04", "partners")
    assert step.register_ == {"es": "T", "fr": "T", "de": "T"}
    assert b.fictional.brands == ["Brightwave Energy", "Kappa Cola"]
    assert b.story_overrides[0].story_day == 0


def test_unknown_keys_are_warnings():
    r = parse_bible(MIN + "mood: dark\n")
    assert r.ok and r.warnings == ["Unknown key 'mood'"]
    r = parse_bible("show: s\ncharacters:\n  - {id: a, name: A, height: tall}\n")
    assert r.ok and r.warnings == ["Unknown key 'characters[0].height'"]


def test_schema_errors():
    r = parse_bible("characters: []\n")  # show missing
    assert [e.reason.split(":")[0] for e in r.errors] == ["show"]
    r = parse_bible("show: s\ncharacters:\n  - {id: a, name: A, identity_hidden_until: ep8}\n")
    assert not r.ok and r.errors[0].reason.startswith("characters.0.identity_hidden_until")
    r = parse_bible("show: s\ncharacters:\n  - {name: A}\n")
    assert not r.ok and r.errors[0].reason.startswith("characters.0.id")


def test_cross_references_and_duplicates():
    r = parse_bible(MIN + "relationships:\n  - between: [a, zed]\n")
    assert [e.reason for e in r.errors] == ["Relationship references unknown character 'zed'"]
    r = parse_bible("show: s\ncharacters:\n  - {id: a, name: A}\n  - {id: a, name: B}\n")
    assert [e.reason for e in r.errors] == ["Duplicate character id 'a'"]
    r = parse_bible(MIN + "secrets:\n  - {id: x, description: d}\n  - {id: x, description: e}\n")
    assert [e.reason for e in r.errors] == ["Duplicate secret id 'x'"]


def test_yaml_syntax_and_shape():
    r = parse_bible("show: s\ncharacters: [unclosed\nmore: 1\n")
    assert not r.ok and r.errors[0].line is not None
    r = parse_bible("- just\n- a list\n")
    assert not r.ok and r.errors[0].line == 1
    assert parse("yaml", MIN.encode()).ok
