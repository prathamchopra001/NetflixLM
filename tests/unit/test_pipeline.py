import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nip.agents.base import Input
from nip.cli import app
from nip.contracts.flag import Agent
from nip.contracts.report import Report
from nip.pipeline import InputRejected, build_checks, coverage, run_pipeline

SCRIPT = "INT. ROOM - DAY #1#\n\nMaya enters.\n\nEXT. DOCK - NIGHT #2#\n\nRain.\n"
EN = "1\n00:00:01,000 --> 00:00:03,000\nHello.\n\n2\n00:00:04,000 --> 00:00:06,000\nBye.\n"
# cue 2 has 3 lines; cue 3 starts 1 frame after cue 2 ends
ES = (
    "1\n00:00:01,000 --> 00:00:03,000\nHola.\n\n"
    "2\n00:00:04,000 --> 00:00:06,000\nuno\ndos\ntres\n\n"
    "3\n00:00:06,042 --> 00:00:08,000\nAdiós.\n"
)


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
    assert summary["flags_kept"] == 2 and summary["dropped"] == [] and summary["skipped"] == []
    assert [s["stage"] for s in summary["stages"]] == [
        "ingest",
        "picture",
        "timeline",
        "loc.readability",
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
    assert s["skipped"] == ["loc.readability"] and s["flags_kept"] == 0


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
    ctx = {"langs": ["es"], "conn": None, "show": None}
    checks, skipped = build_checks(subs, ctx)
    assert [str(c.check) for c in checks] == ["loc.readability"] and skipped == []
    assert build_checks({Input.TARGET_SUBS}, ctx) == ([], ["loc.readability"])
    assert build_checks(subs, ctx, agents={Agent.SCRIPT_CRITIC}) == ([], [])
    with pytest.raises(InputRejected, match="no readability rule pack for language 'xx'"):
        build_checks(subs, ctx | {"langs": ["xx"]})


def test_coverage_counts_done_units_per_agent() -> None:
    checks, _ = build_checks({Input.SOURCE_SUBS, Input.TARGET_SUBS}, {"langs": ["es"]})
    units = [{"stage": "loc.readability", "status": s} for s in ("done", "done", "failed", "done")]
    assert coverage(checks, [], units) == {Agent.LOCALIZATION_AUDITOR: 0.75}
    assert coverage(checks, [], []) == {Agent.LOCALIZATION_AUDITOR: 1.0}  # active, nothing to do
    assert coverage([], ["loc.readability"], []) == {Agent.LOCALIZATION_AUDITOR: 0.0}
