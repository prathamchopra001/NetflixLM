import json
from typing import Any

import pytest
from pydantic import ValidationError

from nip.agents.base import Finding, emit
from nip.contracts.flag import (
    Agent,
    CheckId,
    Evidence,
    EvidenceKind,
    Flag,
    ProducedBy,
    Tier,
)
from nip.contracts.report import Report, ReportPlan, build_report
from nip.ingest import parse_srt
from nip.ingest.script import Scene, Script
from nip.timeline.estimate import build_timeline

# docs/api-contracts.md › GET /shows/{show}/episodes/{ep}/report (one summary filled in).
DOC_REPORT: dict[str, Any] = {
    "episode": "S01E03", "run_id": "run_912", "status": "completed_with_gaps",
    "plan": {"plan_id": "plan_42", "mode": "staged", "judge_independent": False},
    "coverage": {"localization_auditor": 1.0, "clearance_scanner": 0.983,
                 "script_critic": 1.0, "continuity_inspector": 1.0},
    "counts": {"must_review": 9, "review_recommended": 14, "suppressed": 22},
    "sections": [
        {"category": "clearance", "flags": [
            {"id": "flg_48213", "check": "clr.phone", "severity": 4, "confidence": 0.96,
             "tier": "must_review", "title": "Real-format phone number visible on shop sign",
             "lang": None, "primary_tc": "00:12:04:08", "status": "open"}]},
        {"category": "continuity", "flags": []},
        {"category": "localization", "flags": []},
        {"category": "plot_hole", "flags": []},
    ],
}  # fmt: skip

PB = ProducedBy(model_variant=None, plan_id="plan_42")
PLAN = ReportPlan(plan_id="plan_42", mode="staged", judge_independent=False)


def test_documented_report_validates_and_round_trips() -> None:
    r = Report.model_validate(DOC_REPORT)
    # W-serve added skipped_slots / warnings to the plan header (additive, empty by default)
    plan = DOC_REPORT["plan"] | {"skipped_slots": [], "warnings": []}
    assert json.loads(r.model_dump_json()) == DOC_REPORT | {"plan": plan}


@pytest.mark.parametrize(
    ("path", "value"),
    [(("status",), "done"), (("coverage", "localization_auditor"), 1.2),
     (("counts", "hidden"), 1), (("sections", 0, "category"), "music")],
)  # fmt: skip
def test_report_rejects_off_contract_values(path: tuple[Any, ...], value: Any) -> None:
    bad = json.loads(json.dumps(DOC_REPORT))
    node = bad
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    with pytest.raises(ValidationError):
        Report.model_validate(bad)


def _flag(check: str, severity: int, confidence: float, tier: str, ref: str = "x") -> Flag:
    agent, category = {
        "clr": ("clearance_scanner", "clearance"),
        "loc": ("localization_auditor", "localization"),
        "plot": ("script_critic", "plot_hole"),
    }[check.split(".")[0]]
    return Flag.model_validate(
        {"run_id": "run_1", "episode": "S01E03", "agent": agent, "check": check,
         "category": category, "severity": severity, "confidence": confidence, "tier": tier,
         "title": f"{check} {severity} {confidence}", "explanation": "e",
         "evidence": [{"kind": "subtitle_cue", "ref": ref, "role": "claim",
                       "tc_in": "00:00:01:00"}],
         "produced_by": {"model_variant": None, "plan_id": "plan_42"}}
    )  # fmt: skip


def test_build_report_ranks_by_consequence_severity_confidence() -> None:
    flags = [
        _flag("loc.readability", 2, 0.99, "must_review"),
        _flag("plot.dead_acts", 5, 0.95, "must_review"),
        _flag("loc.spoiler", 5, 0.75, "review_recommended"),
        _flag("loc.term", 5, 0.92, "must_review"),
        _flag("clr.phone", 1, 0.91, "must_review"),
        _flag("loc.gender", 5, 0.40, "suppressed"),
    ]
    r = build_report(
        episode="S01E03", run_id="run_1", status="completed", plan=PLAN,
        coverage={Agent.LOCALIZATION_AUDITOR: 1.0}, flags=flags,
    )  # fmt: skip
    titles = {s.category.value: [f.title for f in s.flags] for s in r.sections}
    assert list(titles) == ["clearance", "continuity", "localization", "plot_hole"]
    assert titles == {
        "clearance": ["clr.phone 1 0.91"],
        "continuity": [],
        "localization": ["loc.term 5 0.92", "loc.spoiler 5 0.75", "loc.readability 2 0.99"],
        "plot_hole": ["plot.dead_acts 5 0.95"],
    }
    assert r.counts == {Tier.MUST_REVIEW: 4, Tier.REVIEW_RECOMMENDED: 1, Tier.SUPPRESSED: 1}

    with_suppressed = build_report(
        episode="S01E03", run_id="run_1", status="completed", plan=PLAN,
        coverage={}, flags=flags, include_suppressed=True,
    )  # fmt: skip
    assert len(with_suppressed.sections[2].flags) == 4
    assert with_suppressed.counts == r.counts


def test_report_json_from_emitted_flags_has_resolvable_evidence() -> None:
    subs = parse_srt("1\n00:00:01,000 --> 00:00:02,000\nHola\n").data
    assert subs
    tl = build_timeline(
        "S01E03", Script(None, [Scene("12", "INT. A - DAY")]), subtitles={"es": subs}
    )
    cue = Evidence(kind=EvidenceKind.SUBTITLE_CUE, ref="S01E03/es/1", role="claim", quote="Hola")
    scene = Evidence(kind=EvidenceKind.SCENE, ref="S01E03/sc/12", role="claim")
    flags = [
        emit(Finding(3, 0.95, "cue", "e", [cue], lang="es"), CheckId.LOC_READABILITY, tl, "r", PB),
        emit(Finding(3, 0.80, "scene", "e", [scene]), CheckId.PLOT_DEAD_ACTS, tl, "r", PB),
    ]
    r = build_report(
        episode="S01E03", run_id="r", status="completed", plan=PLAN,
        coverage={Agent.LOCALIZATION_AUDITOR: 1.0, Agent.SCRIPT_CRITIC: 1.0},
        flags=[f for f in flags if f],
    )  # fmt: skip
    doc = json.loads(r.model_dump_json())
    assert Report.model_validate(doc) == r
    loc, plot = doc["sections"][2]["flags"], doc["sections"][3]["flags"]
    assert loc == [{"id": None, "check": "loc.readability", "severity": 3, "confidence": 0.95,
                    "tier": "must_review", "title": "cue", "lang": "es",
                    "primary_tc": "00:00:01:00", "status": "open"}]  # fmt: skip
    assert plot[0]["primary_tc"] == "S01E03 · Sc 12 (script estimate)"
    assert plot[0]["tier"] == "review_recommended"
    assert doc["coverage"] == {"localization_auditor": 1.0, "script_critic": 1.0}
