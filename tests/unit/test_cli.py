import json

import pytest
from typer.testing import CliRunner

from nip.cli import app


def test_root_help() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Netflix LM pre-release QA pipeline" in result.output
    for cmd in ("ingest", "run", "run-files", "eval", "timeline", "plan"):
        assert f"\n  {cmd} " in result.output, cmd  # plain Click layout (Rich off: conftest)


def test_eval_nests_corpus_and_labels() -> None:
    result = CliRunner().invoke(app, ["eval", "--help"])
    assert result.exit_code == 0
    for cmd in ("run", "compare", "corpus", "labels"):
        assert f" {cmd} " in result.output, cmd


def test_run_takes_show_and_episodes() -> None:
    result = CliRunner().invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    for opt in ("--show", "--episodes", "--agents", "--force", "--out-dir"):
        assert opt in result.output, opt


def test_phase2_sub_apps_are_wired() -> None:
    assert " inject " in CliRunner().invoke(app, ["eval", "--help"]).output
    out = CliRunner().invoke(app, ["timeline", "--help"]).output
    for cmd in ("picture", "asr", "align"):
        assert f" {cmd} " in out, cmd


def test_dry_run_prints_the_wired_stage_order_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from nip import pipeline

    monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
    monkeypatch.setattr(pipeline, "AGENTS", list(pipeline.AGENTS))
    args = ["run", "--show", "x", "--episodes", "S01E01", "--dry-run"]
    for _ in range(2):  # wire() is idempotent
        r = CliRunner().invoke(app, args)
        assert r.exit_code == 0, r.output
    got = json.loads(r.output)
    assert got["stages"] == [
        "timeline.asr", "timeline.align", "knowledge.story", "knowledge.extract",
        "knowledge.consolidate", "knowledge.index", "timeline", "timeline.cue_align",
        "loc.observed", "clearance.ocr", "checks", "verification", "flags", "clearance.csv",
        "report",
    ]  # fmt: skip
    assert {c.split(".")[0] for c in got["checks"]} == {"loc", "plot", "clr"}
    assert "plot.dead_acts" in got["checks"] and "loc.term" in got["checks"]
