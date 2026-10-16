import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nip import pipeline
from nip.agents.base import Input
from nip.cli import app
from nip.contracts import Autoscaling, Gpu, HardwareInventory, Node, Plan, Slot, StageGroup
from nip.contracts.flag import Agent, Flag
from nip.contracts.report import Report
from nip.pipeline import (
    InputRejected,
    build_checks,
    coverage,
    require_stable_refs,
    run_pipeline,
)
from nip.runtime import planner
from nip.runtime.catalog import load_catalog

SCRIPT = "INT. ROOM - DAY #1#\n\nMaya enters.\n\nEXT. DOCK - NIGHT #2#\n\nRain.\n"
EN = "1\n00:00:01,000 --> 00:00:03,000\nHello.\n\n2\n00:00:04,000 --> 00:00:06,000\nBye.\n"
# cue 2 has 3 lines; cue 3 starts 1 frame after cue 2 ends
ES = (
    "1\n00:00:01,000 --> 00:00:03,000\nHola.\n\n"
    "2\n00:00:04,000 --> 00:00:06,000\nuno\ndos\ntres\n\n"
    "3\n00:00:06,042 --> 00:00:08,000\nAdiós.\n"
)


# 2.4's checks that need more than script + subtitles: loc.term (bible or glossary) and
# loc.shot_change (picture); drift and offset run on subtitles alone
NEEDS_MORE = ["loc.term", "loc.shot_change"]


def _files(tmp_path: Path, script: str = SCRIPT) -> dict[str, Path]:
    for name, text in [("s.fountain", script), ("en.srt", EN), ("es.srt", ES)]:
        (tmp_path / name).write_text(text, encoding="utf-8")
    return {"script": tmp_path / "s.fountain", "en": tmp_path / "en.srt", "es": tmp_path / "es.srt"}


def test_script_and_subtitles_run_end_to_end(tmp_path: Path) -> None:
    f = _files(tmp_path)
    out = tmp_path / "out"
    summary = run_pipeline(
        episode="E1",
        script=f["script"],
        subs={"en": f["en"], "es": f["es"]},
        source_lang="en",
        out_dir=out,
    )
    assert summary["flags_kept"] == 2 and summary["dropped"] == []
    assert summary["skipped"] == NEEDS_MORE  # no picture, bible or glossary
    assert [s["stage"] for s in summary["stages"]] == [
        "ingest",
        "picture",
        "timeline",
        "loc.readability",
        "loc.drift",
        "loc.offset",
        "verification",
        "report",
    ]
    report = Report.model_validate_json((out / "report.json").read_text(encoding="utf-8"))
    loc = next(s for s in report.sections if s.category == "localization")
    assert [(x.title, x.primary_tc) for x in loc.flags] == [
        ("Cue 2: 3 lines (max 2)", "00:00:04:00"),
        ("Cue 3: gap of 1 frames (min 2)", "00:00:06:01"),
    ]
    flags = [json.loads(x) for x in (out / "flags.jsonl").read_text().splitlines()]
    tl = json.loads((out / "timeline.json").read_text())
    spans = {s["ref"]: s for s in tl["spans"]}
    for fl in flags:  # every evidence ref resolves to a span of the written timeline
        assert fl["verification"]["evidence"] == "pass"
        assert fl["verification"]["rule_recheck"] == "pass"
        for ev in fl["evidence"]:
            assert spans[ev["ref"]]["frames"] == ev["frames"]


def test_without_source_track_the_check_is_skipped(tmp_path: Path) -> None:
    f = _files(tmp_path)
    s = run_pipeline(
        episode="E1", script=f["script"], subs={"es": f["es"]}, source_lang="en", out_dir=tmp_path
    )
    assert s["skipped"] == ["loc.readability", *NEEDS_MORE, "loc.drift", "loc.offset"]
    assert s["flags_kept"] == 0


def test_duplicate_scene_numbers_are_rejected(tmp_path: Path) -> None:
    f = _files(tmp_path, SCRIPT.replace("#2#", "#1#"))
    with pytest.raises(InputRejected, match=r"duplicate scene numbers \['1'\]"):
        run_pipeline(episode="E1", script=f["script"], subs={}, source_lang="en", out_dir=tmp_path)


def test_cli_reports_rejected_input(tmp_path: Path) -> None:
    f = _files(tmp_path)
    (tmp_path / "bad.srt").write_text("1\n00:00:05,000 --> 00:00:01,000\nx\n", encoding="utf-8")
    args = [
        "run-files",
        "--episode",
        "E1",
        "--script",
        str(f["script"]),
        "--out-dir",
        str(tmp_path),
    ]
    res = CliRunner().invoke(
        app, [*args, "--subs", f"en={f['en']}", "--subs", f"es={tmp_path / 'bad.srt'}"]
    )
    assert res.exit_code == 1
    assert "INPUT_REJECTED: bad.srt: cue 1: end" in res.output


def test_cli_run_writes_report(tmp_path: Path) -> None:
    f = _files(tmp_path)
    args = [
        "run-files",
        "--episode",
        "E1",
        "--script",
        str(f["script"]),
        "--out-dir",
        str(tmp_path),
    ]
    res = CliRunner().invoke(app, [*args, "--subs", f"en={f['en']}", "--subs", f"es={f['es']}"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["flags_kept"] == 2


def test_files_must_fit_their_role(tmp_path: Path) -> None:
    f = _files(tmp_path)
    with pytest.raises(InputRejected, match="en.srt: a srt file is not a Script"):
        run_pipeline(episode="E1", script=f["en"], subs={}, source_lang="en", out_dir=tmp_path)
    with pytest.raises(InputRejected, match="s.fountain: a fountain file is not a SubtitleTrack"):
        run_pipeline(
            episode="E1", script=f["script"], subs={"es": f["script"]}, source_lang="en",
            out_dir=tmp_path,
        )  # fmt: skip


def test_cli_picture_must_be_a_file(tmp_path: Path) -> None:
    f = _files(tmp_path)
    args = [
        "run-files",
        "--episode",
        "E1",
        "--script",
        str(f["script"]),
        "--out-dir",
        str(tmp_path),
    ]
    res = CliRunner().invoke(app, [*args, "--subs", f"en={f['en']}", "--picture", str(tmp_path)])
    assert res.exit_code == 2 and "is a directory" in res.output


def test_checks_come_from_agent_packages_and_activation() -> None:
    subs = {Input.SOURCE_SUBS, Input.TARGET_SUBS}
    ctx = {"langs": ["es"], "source_lang": "en", "conn": None, "show": None}
    checks, skipped = build_checks(subs, ctx)
    assert [str(c.check) for c in checks] == ["loc.readability", "loc.drift", "loc.offset"]
    assert skipped == NEEDS_MORE
    skipped_all = ["loc.readability", *NEEDS_MORE, "loc.drift", "loc.offset"]
    assert build_checks({Input.TARGET_SUBS}, ctx) == ([], skipped_all)
    assert build_checks(subs, ctx, agents={Agent.SCRIPT_CRITIC}) == ([], [])
    with pytest.raises(InputRejected, match="no readability rule pack for language 'xx'"):
        build_checks(subs, ctx | {"langs": ["xx"]})


def test_coverage_counts_done_units_per_agent() -> None:
    ctx = {"langs": ["es"], "source_lang": "en"}
    checks, _ = build_checks({Input.SOURCE_SUBS, Input.TARGET_SUBS}, ctx)
    units = [{"stage": "loc.readability", "status": s} for s in ("done", "done", "failed", "done")]
    assert coverage(checks, [], units) == {Agent.LOCALIZATION_AUDITOR: 0.75}
    assert coverage(checks, [], []) == {Agent.LOCALIZATION_AUDITOR: 1.0}  # active, nothing to do
    assert coverage([], ["loc.readability"], []) == {Agent.LOCALIZATION_AUDITOR: 0.0}


def test_flags_without_a_stable_or_valid_ref_are_counted_drops() -> None:
    def flag(*refs: tuple[str, str]) -> Flag:
        ev = [{"kind": k, "ref": r, "role": "claim"} for k, r in refs]
        return Flag.model_validate({
            "run_id": "r", "episode": "E1", "agent": "script_critic",
            "check": "plot.knowledge_order", "category": "plot_hole", "severity": 3,
            "confidence": 0.9, "tier": "must_review", "title": "t", "explanation": "e",
            "evidence": ev, "produced_by": {"model_variant": None, "plan_id": "p"},
        })  # fmt: skip

    good = flag(("script_line", "E1/line/1.2"), ("fact", "fact/3"))
    ok, bad = require_stable_refs(
        [good, flag(("fact", "fact/3")), flag(("scene", "E1/scene/oops/x"))]
    )
    assert ok == [good]
    assert [r.split(":")[0] for _, r in bad] == [
        "no stable evidence ref (scene/line/shot/kf/cue/clr), R13",
        "malformed evidence ref",
    ]


# ---- W-serve: skipped slots are recorded, staged segments, the no-fit reason ------------------
def _inv(free_gb: float) -> HardwareInventory:
    gpu = Gpu(index=0, name="g", vram_total_gb=8.0, vram_free_gb=free_gb, compute_capability="8.9")
    return HardwareInventory(
        fingerprint="sim",
        nodes=[Node(node_id="n0", cpus=16, ram_gb=31.0, gpus=[gpu])],
        autoscaling=Autoscaling(enabled=False, max_gpu_nodes=0),
    )


WORKLOAD = {s: 1 for s in pipeline.MODEL_SLOTS}
PINS = {Slot.ASR: "faster-whisper-large-v3-turbo-int8"}
CATALOG = load_catalog()


def _plan(free_gb: float) -> Plan:
    return planner.plan(_inv(free_gb), CATALOG, WORKLOAD, pins=PINS, margin_gb=pipeline.MARGIN_GB)


def test_no_fit_says_free_vs_needed() -> None:
    """W-int's laptop reading (6.70 GiB free): text_llm is skipped, and the reason has numbers."""
    p = _plan(6.70)
    assert p.skipped_slots == [Slot.TEXT_LLM]
    why = pipeline.no_fit(Slot.TEXT_LLM, _inv(6.70), CATALOG, PINS, 0.9)
    assert why == (
        "no hardware for text_llm: qwen3.5-4b-awq needs 6.25 GiB on one GPU, GPU 0 has 6.20 "
        "usable = min(0.90 x 8.00 total, 6.70 free - 0.50 margin): short 0.05 GiB"
    )
    assert Slot.TEXT_LLM in _plan(6.75).decisions  # the reason's arithmetic is the planner's


def test_a_skipped_slot_skips_its_stages_and_story_runs_on_rules() -> None:
    p = _plan(6.70)
    p = p.model_copy(update={"warnings": ["no hardware for text_llm: short 0.05 GiB"]})
    names = ["timeline.asr", "knowledge.story", "knowledge.extract", "knowledge.index", "checks"]
    assert pipeline.skipped_stages(p, names) == {
        "knowledge.story": "knowledge.story ran on rules only: no hardware for text_llm: "
        "short 0.05 GiB",
        "knowledge.extract": "knowledge.extract skipped: no hardware for text_llm: short 0.05 GiB",
    }
    rp = pipeline.report_plan(p, ["note"])
    assert rp.skipped_slots == [Slot.TEXT_LLM] and rp.warnings[-1] == "note"


def test_outside_the_cluster_llm_slots_are_skipped_with_the_reason() -> None:
    p = _plan(7.6)
    assert pipeline.serve_slots(p) == {Slot.TEXT_LLM}  # asr/embedder run in-process
    q = pipeline.without(p, {Slot.TEXT_LLM}, "run it in the cluster")
    assert Slot.TEXT_LLM not in q.decisions and q.skipped_slots == [Slot.TEXT_LLM]
    assert all(Slot.TEXT_LLM not in g.slots and g.slots for g in q.groups)
    assert pipeline.slot_reason(q, Slot.TEXT_LLM) == "no Serve for text_llm: run it in the cluster"


def test_segments_cut_where_the_served_group_changes() -> None:
    p = _plan(7.6)
    llm = next(g for g in p.groups if Slot.TEXT_LLM in g.slots)
    assert p.mode == "staged" and llm.name == "llm"
    names = ["timeline.asr", "timeline.align", "knowledge.story", "knowledge.extract",
             "knowledge.consolidate", "knowledge.index", "timeline"]  # fmt: skip
    stages = [(n, lambda ep: None) for n in names]

    def cut(served: dict[Slot, StageGroup]) -> list[tuple[str | None, list[str]]]:
        segs = pipeline.segments(stages, served)  # type: ignore[arg-type]
        return [(g.name if g else None, [n for n, _ in part]) for g, part in segs]

    assert cut({Slot.TEXT_LLM: llm}) == [
        (None, ["timeline.asr", "timeline.align"]),
        ("llm", ["knowledge.story", "knowledge.extract"]),
        (None, ["knowledge.consolidate", "knowledge.index", "timeline"]),
    ]
    assert cut({}) == [(None, [n for n, _ in stages])]  # no serving: today's per-episode order
