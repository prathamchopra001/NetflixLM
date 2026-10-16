"""NIP_CI=1 (set by .github/workflows/ci.yml): a skipped test fails instead.

Locally a missing ffmpeg/TorchCodec or test database skips its tests; in CI that would turn
"green" into "never ran", so every skip of a selected test is reported as a failure there.
"""

import os
from collections.abc import Generator

import pytest


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    if os.environ.get("NIP_CI") == "1" and report.skipped and not hasattr(report, "wasxfail"):
        report.outcome = "failed"
        report.longrepr = f"NIP_CI=1: skipped tests fail in CI ({report.longrepr})"
    return report
