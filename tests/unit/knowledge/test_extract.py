"""Extraction unit: prompt, enum schema, structural repair rule, value mapping, recorded stub."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, Field, ValidationError

from nip.knowledge.extract import (
    Entry,
    Line,
    SceneText,
    event_schema,
    extract_scene,
    holds_verb,
    render,
    request,
    value_json,
)
from nip.runtime.clients import StubLLM
from nip.runtime.clients import stub as stubs

REGISTRY = [
    Entry(
        "maya",
        "character",
        "Maya Reyes",
        ("May", "the detective"),
        {"gender": "female", "pronouns": {"en": "she/her"}},
    ),
    Entry("leo", "character", "Leo Park", ("Lee",), {"gender": "male"}),
    Entry("secret_1", "secret", "secret_1", (), {"description": "Ada Kovac is the informant"}),
    Entry("Harbor Warehouse", "location", "Harbor Warehouse"),
]
SCENE = SceneText(
    "S01E01/sc/3",
    "INT. HARBOR WAREHOUSE - NIGHT",
    [
        Line(1, "action", "Maya waits at Harbor Warehouse, sleepless."),
        Line(2, "dialogue", "So it is true. Ada Kovac is the informant.", "MAYA"),
    ],
)


def test_prompt_numbers_lines_names_speakers_and_lists_only_present_characters() -> None:
    p = render(SCENE, REGISTRY)
    assert "[1] (action) Maya waits at Harbor Warehouse, sleepless." in p
    assert "[2] MAYA: So it is true. Ada Kovac is the informant." in p
    assert "- secret_1 (secret): Ada Kovac is the informant" in p
    assert "- maya: Maya Reyes; female, she/her" in p
    assert "- leo:" not in p  # "Lee" is not a word of "sleepless"
    assert "registry keys" in p and "registry keys" not in render(SCENE, REGISTRY, enum=False)


def test_schema_constrains_ids_to_the_registry_plus_unknown() -> None:
    schema = event_schema([e.key for e in REGISTRY])
    ev = {"line": 2, "quote": "x", "predicate": "learns", "subject": "maya", "confidence": 0.9}
    schema.model_validate({"events": [ev | {"object": "UNKNOWN", "object_name": "Ada"}]})
    with pytest.raises(ValidationError):
        schema.model_validate({"events": [ev | {"subject": "Maya"}]})
    js = json.dumps(schema.model_json_schema())
    assert '"enum": ["maya", "leo", "secret_1", "Harbor Warehouse", "UNKNOWN"]' in js
    free = event_schema(None)
    free.model_validate({"events": [ev | {"subject": "Maya"}]})


def test_events_are_capped_per_scene_line() -> None:  # 2.1B runaway guard (xgrammar maxItems)
    ev = {"line": 1, "quote": "x", "predicate": "decision", "subject": "a", "confidence": 1}
    schema = event_schema(None, 2)
    schema.model_validate({"events": [ev, ev]})
    with pytest.raises(ValidationError):
        schema.model_validate({"events": [ev, ev, ev]})
    assert '"maxItems": 2' in json.dumps(schema.model_json_schema())
    _, sch = request(SCENE, REGISTRY)
    js = sch.model_json_schema()
    assert js["properties"]["events"]["maxItems"] == 8  # 4 x 2 lines
    assert js["$defs"]["Event"]["properties"]["line"]["enum"] == [1, 2]  # 2.1B: only its lines


def test_a_multi_paragraph_line_prints_as_one_numbered_line() -> None:  # review I1
    sc = SceneText("S01E01/sc/4", "INT. PIER NINE - NIGHT",
                   [Line(1, "action", "Dov waits.\n\nDov checks the signal flare again."),
                    Line(2, "dialogue", "Ready.", "DOV")])  # fmt: skip
    p = render(sc, REGISTRY)
    assert "[1] (action) Dov waits. Dov checks the signal flare again.\n[2] DOV: Ready." in p


def test_a_line_outside_the_scene_is_a_structural_error() -> None:
    schema = event_schema(None)
    ev = {"line": 7, "quote": "x", "predicate": "decision", "subject": "a", "confidence": 1}
    with pytest.raises(ValidationError, match="not a line of this scene"):
        schema.model_validate({"events": [ev]}, context={"lines": {1, 2}})
    schema.model_validate({"events": [ev]})  # no context: not checked


class FakeLLM:
    variant = "fake"

    def __init__(self, reply: dict[str, Any]) -> None:
        self.reply, self.calls = reply, []  # type: list[Any]

    def complete(self, prompt: str, schema: type[BaseModel], **kw: Any) -> BaseModel:
        self.calls.append((prompt, kw))
        return schema.model_validate(self.reply, context=kw.get("context"))


def test_extract_scene_returns_raw_events_with_the_scene_ref() -> None:
    ev = {
        "line": 2,
        "quote": "Ada Kovac is the informant",
        "predicate": "learns",
        "subject": "maya",
        "object": "secret_1",
        "confidence": 0.95,
    }
    llm = FakeLLM({"events": [ev]})
    [raw] = extract_scene(llm, SCENE, REGISTRY)  # type: ignore[arg-type]
    assert raw["scene"] == "S01E01/sc/3" and raw["object"] == "secret_1" and raw["value"] is None
    assert llm.calls[0][1]["context"] == {"lines": {1, 2}}


def test_value_text_maps_to_the_fact_value_shape() -> None:
    assert value_json("state", "injured: left hand cut") == {
        "state": "injured",
        "detail": "left hand cut",
    }
    assert value_json("holds", "obtain") == {"event": "obtain"}
    # the line's verb mapped to the prompt's vocabulary (fix round 1, re-review N2)
    assert value_json("holds", "check") == {"event": "use", "detail": "check"}
    assert value_json("holds", "picks up") == {"event": "obtain", "detail": "picks up"}
    assert value_json("owns", "lose") == {"event": "lose"}
    assert value_json("holds", "removes") == {"event": "remove", "detail": "removes"}  # ends it
    assert value_json("holds", "gives: to Ada") == {"event": "give", "detail": "to Ada"}
    for verb in ("share", "receives", "steals", "take"):  # not defined: dropped, never a use
        assert holds_verb(verb) is None
    assert value_json("setup", "3") == {"importance": 3}
    assert value_json("relationship", "partners") == {"kind": "partners"}
    assert value_json("decision", "leave the city") == {"detail": "leave the city"}
    assert value_json("present_at", " ") is None and value_json("learns", None) is None


class Answer(BaseModel):
    n: int = Field(gt=0, le=5)


def test_stub_replays_a_recording_else_the_minimal_instance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(stubs, "FIXTURES", tmp_path)
    assert StubLLM().complete("q?", Answer) == Answer(n=1)
    key = stubs.record_key(stubs.REPLAY_VARIANT, "q?", Answer, None)
    stubs.record(key, stubs.REPLAY_VARIANT, "Answer", '{"n": 4}', tmp_path)
    assert StubLLM().complete("q?", Answer) == Answer(n=4)
    assert StubLLM().complete("q?", Answer, system="other") == Answer(n=1)  # another key


class Bounds(BaseModel):
    half: float = Field(gt=0, le=0.5)
    neg: int = Field(le=-3)
    below: float = Field(lt=0)
    short: str = Field(max_length=2)


def test_stub_instance_respects_numeric_bounds_and_max_length() -> None:  # 1.7 review M5
    assert stubs.stub_instance(Bounds) == Bounds(half=0.25, neg=-3, below=-1, short="st")
