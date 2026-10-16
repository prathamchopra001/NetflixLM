from typer.testing import CliRunner

from nip.cli import app


def test_root_help() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Netflix LM pre-release QA pipeline" in result.output
    for cmd in ("run", "eval", "timeline", "plan"):
        assert f"│ {cmd} " in result.output or f"| {cmd} " in result.output, cmd


def test_eval_nests_corpus_and_labels() -> None:
    result = CliRunner().invoke(app, ["eval", "--help"])
    assert result.exit_code == 0
    for cmd in ("run", "compare", "corpus", "labels"):
        assert f" {cmd} " in result.output, cmd
