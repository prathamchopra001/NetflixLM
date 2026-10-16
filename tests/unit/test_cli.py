from typer.testing import CliRunner

from nip.cli import app


def test_root_help() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Netflix LM pre-release QA pipeline" in result.output
    for cmd in ("ingest", "run", "run-files", "eval", "timeline", "plan"):
        assert f"│ {cmd} " in result.output or f"| {cmd} " in result.output, cmd


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
