"""The derived as-broadcast scripts (R5) and their EXP-004 labels agree with each other."""

import json
from pathlib import Path

import pytest

from nip.ingest.script import parse_fountain
from nip.timeline.align import dialogue

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("title", ["sintel", "tears-of-steel"])
def test_derived_script_matches_its_labels(title):
    parsed = parse_fountain((ROOT / f"eval/corpus/derived/{title}/script.fountain").read_bytes())
    assert parsed.data is not None and not parsed.errors
    labels = [
        json.loads(x)
        for x in (ROOT / f"eval/exp/exp004_labels/{title}.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    scenes = parsed.data.scenes
    assert len(labels) == sum(len(s.elements) for s in scenes) > 20
    for lab in labels:
        e = scenes[lab["scene"]].elements[lab["element"]]
        assert e.kind == "dialogue" and e.text == lab["text"]
        assert lab["labeller"] == "agent"
    starts = [lab["start_frame"] for lab in labels]
    assert starts == sorted(starts)  # monotone: the script is in broadcast order
    assert len(dialogue(parsed.data)) == len(labels)
