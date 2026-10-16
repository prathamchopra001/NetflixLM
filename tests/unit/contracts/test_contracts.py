import copy
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from nip.contracts import Fact, Flag, HardwareInventory, Plan

# Examples copied from docs/data-model.md and docs/hardware-adaptation.md.
FLAG: dict[str, Any] = {
    "id": "flg_48213",
    "run_id": "run_912",
    "episode": "S01E03",
    "agent": "clearance_scanner",
    "check": "clr.phone",
    "category": "clearance",
    "lang": None,
    "severity": 4,
    "confidence": 0.96,
    "tier": "must_review",
    "title": "Real-format phone number visible on shop sign",
    "explanation": "OCR reads '(617) 4XX-XXXX' on the storefront sign for 6.2 s (featured).",
    "suggested_fix": "Replace with a number in 555-0100–0199, or blur in post.",
    "evidence": [
        {"kind": "keyframe", "ref": "S01E03/kf/118.0", "role": "claim",
         "tc_in": "00:12:04:08", "tc_out": "00:12:10:13",
         "quote": "(617) 4XX-XXXX",
         "crop": {"keyframe": "S01E03/kf/118.0", "box": [0.61, 0.22, 0.12, 0.09]}},
        {"kind": "shot", "ref": "S01E03/shot/118", "role": "context",
         "tc_in": "00:12:04:08", "tc_out": "00:12:10:13"},
    ],
    "produced_by": {"model_variant": "pp-ocrv6-medium", "prompt_version": None,
                    "plan_id": "plan_42", "cache_key": "9f1c…"},
    "verification": {"evidence": "pass", "rule_recheck": "pass", "judge": "n/a"},
    "status": "open",
    "disposition": None,
}  # fmt: skip

INVENTORY: dict[str, Any] = {
    "fingerprint": "sha256:5c1e…",
    "nodes": [
        {"node_id": "a1f3…", "cpus": 16, "ram_gb": 23.5,
         "gpus": [{"index": 0, "name": "NVIDIA GeForce RTX 4060 Laptop GPU",
                   "vram_total_gb": 8.0, "vram_free_gb": 7.15, "compute_capability": "8.9"}]},
    ],
    "autoscaling": {"enabled": False, "max_gpu_nodes": 0, "node_type": None},
}  # fmt: skip

PLAN: dict[str, Any] = {
    "plan_id": "plan_42",
    "inventory_fingerprint": "sha256:5c1e…",
    "catalog_sha256": "b07d…",
    "objective": "quality",
    "mode": "staged",
    "groups": [
        {"name": "timeline", "slots": ["shot_detector", "asr"]},
        {"name": "vision_prep", "slots": ["ocr", "detector", "image_embedder"]},
        {"name": "text_prep", "slots": ["text_embedder", "ner"]},
        {"name": "vlm+llm", "slots": ["vlm", "text_llm"]},
        {"name": "judge", "slots": ["judge_llm"]},
    ],
    "decisions": {
        "text_llm": {"variant": "qwen3.5-4b-awq", "shared_with": ["vlm"], "replicas": 1,
                     "gpus_per_replica": 1, "context": 8192, "gpu_memory_utilization": 0.83},
        "vlm": {"variant": "qwen3.5-4b-awq", "shared_with": ["text_llm"],
                "max_pixels": 589824, "images_per_prompt": 2},
        "judge_llm": {"variant": "ministral-3-3b-fp8", "independent_family": True, "replicas": 1},
        "asr": {"variant": "faster-whisper-large-v3-int8", "gpu_fraction": 0.5},
        "shot_detector": {"variant": "transnetv2", "gpu_fraction": 0.2},
    },
    "skipped_slots": [],
    "warnings": ["text_llm context reduced 32768 → 8192 to fit 6.65 GB usable VRAM"],
    "amendments": [
        {"at": "2026-10-02T09:41:52Z", "slot": "asr",
         "from": "faster-whisper-large-v3-int8", "to": "faster-whisper-large-v3-turbo-int8",
         "reason": "CUDA OOM persisted after batch reduction"},
    ],
}  # fmt: skip

FACT: dict[str, Any] = {
    "id": 8812,
    "show_id": 1,
    "predicate": "learns",
    "subject_id": 3,
    "object_id": 9,
    "value": None,
    "screen": [(6 << 32) + 44_000, None],
    "story": [211, None],
    "source_event_ids": [501],
    "confidence": 0.94,
    "version": 1,
    "status": "active",
    "supersedes": None,
}


@pytest.mark.parametrize(
    ("model", "example"),
    [(Flag, FLAG), (HardwareInventory, INVENTORY), (Plan, PLAN), (Fact, FACT)],
)
def test_doc_example_round_trips(model: type[BaseModel], example: dict[str, Any]) -> None:
    parsed = model.model_validate(example)
    dumped = parsed.model_dump(mode="json", exclude_unset=True)
    assert model.model_validate(dumped) == parsed
    assert model.model_validate_json(parsed.model_dump_json()) == parsed
    if model is not Plan:  # Plan's amendment timestamp re-serializes as ...Z vs +00:00
        assert dumped == example
    assert model.model_json_schema()  # exported for constrained decoding and the API


def _flag(**changes: Any) -> dict[str, Any]:
    flag = copy.deepcopy(FLAG)
    flag.update(changes)
    return flag


@pytest.mark.parametrize(
    "bad",
    [
        _flag(severity=6),
        _flag(confidence=1.2),
        _flag(check="loc.term"),  # check owned by another agent
        _flag(category="continuity"),
        _flag(check="clr.nonexistent"),
        _flag(evidence=[]),
        _flag(evidence=[{**FLAG["evidence"][1]}]),  # no claim
        _flag(unknown_field=1),
        _flag(disposition={"action": "overridden", "actor": "a", "at": "2026-10-02T12:00:00Z"}),
        _flag(evidence=[{**FLAG["evidence"][0], "frames": [10, 10]}]),  # empty [in, out)
        _flag(evidence=[{**FLAG["evidence"][0], "crop": {"keyframe": "k", "box": [0.1, 0.2]}}]),
    ],
)
def test_flag_rejects(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Flag.model_validate(bad)


def test_layer2_flags_need_two_evidence_items() -> None:
    claim = {"kind": "fact", "ref": "fact/1", "role": "claim"}
    layer2 = _flag(agent="script_critic", check="plot.motivation", category="plot_hole")
    with pytest.raises(ValidationError):
        Flag.model_validate({**layer2, "evidence": [claim]})
    Flag.model_validate({**layer2, "evidence": [claim, {**claim, "role": "context"}]})


def test_flag_defaults_for_emitters() -> None:
    minimal = {k: v for k, v in FLAG.items()
               if k not in {"id", "verification", "status", "disposition"}}  # fmt: skip
    flag = Flag.model_validate(minimal)
    assert flag.id is None
    assert flag.status == "open"
    assert flag.verification.judge == "n/a"


def test_fact_ranges_are_half_open() -> None:
    with pytest.raises(ValidationError):
        Fact.model_validate({**FACT, "story": [211, 211]})
    with pytest.raises(ValidationError):
        Fact.model_validate({**FACT, "source_event_ids": []})


def test_plan_amendment_from_alias() -> None:
    plan = Plan.model_validate(PLAN)
    assert plan.amendments[0].from_ == "faster-whisper-large-v3-int8"
    assert plan.model_dump(mode="json")["amendments"][0]["from"] == plan.amendments[0].from_
