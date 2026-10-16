from typer.testing import CliRunner

from nip.cli import app


def test_root_help() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Netflix LM pre-release QA pipeline" in result.output
