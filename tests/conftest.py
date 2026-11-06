"""NIP_CI=1 (set by .github/workflows/ci.yml): a skipped test fails instead.

Locally a missing ffmpeg/TorchCodec or test database skips its tests; in CI that would turn
"green" into "never ran", so every skip of a selected test is reported as a failure there.

Typer forces Rich colour when GITHUB_ACTIONS is set, which splits "--show" etc. in captured help
text; tests read plain text, so the terminal is forced off before any test imports typer.
"""

import os
from collections.abc import Generator

import pytest

os.environ["_TYPER_FORCE_DISABLE_TERMINAL"] = "1"


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    if os.environ.get("NIP_CI") == "1" and report.skipped and not hasattr(report, "wasxfail"):
        report.outcome = "failed"
        report.longrepr = f"NIP_CI=1: skipped tests fail in CI ({report.longrepr})"
    return report
