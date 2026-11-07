from pathlib import Path

import pytest

pytest_plugins = ["pytester"]


@pytest.mark.parametrize(("ci", "outcome"), [("1", {"failed": 1}), ("", {"skipped": 1})])
def test_skips_fail_under_nip_ci(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch, ci: str, outcome: dict[str, int]
) -> None:
    conftest = Path(__file__).parents[1] / "conftest.py"
    pytester.makeconftest(conftest.read_text(encoding="utf-8"))
    pytester.makepyfile("import pytest\n\ndef test_x():\n    pytest.skip('no ffmpeg')\n")
    monkeypatch.setenv("NIP_CI", ci)
    pytester.runpytest("-p", "no:cacheprovider").assert_outcomes(**outcome)
