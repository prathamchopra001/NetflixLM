"""2.9B `GET /runs/{id}` and `/diff`: auth and the error envelope (shapes: test_rerun.py)."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from nip.api import runs
from tests.unit.api.test_api import assert_unauthorized, client, token

__all__ = ["client"]  # the fixture


@pytest.fixture
def api(client: TestClient) -> TestClient:
    client.app.dependency_overrides[runs.engine] = lambda: MagicMock()  # type: ignore[attr-defined]
    client.app.dependency_overrides[runs.s3] = lambda: MagicMock()  # type: ignore[attr-defined]
    return client


@pytest.mark.parametrize("path", ["/api/v1/runs/run_1", "/api/v1/runs/run_1/diff"])
def test_reading_a_run_needs_a_token_of_any_role(api: TestClient, path: str) -> None:
    assert_unauthorized(api.get(path))


@pytest.mark.parametrize("path", ["/api/v1/runs/flg_1", "/api/v1/runs/run_x/diff"])
def test_an_id_that_is_not_a_run_is_not_found(api: TestClient, path: str) -> None:
    r = api.get(path, headers=token(api, roles=["viewer"]))
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_diff_is_only_against_the_previous_run(api: TestClient) -> None:
    r = api.get("/api/v1/runs/run_1/diff?against=run_0", headers=token(api))
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_FAILED"
