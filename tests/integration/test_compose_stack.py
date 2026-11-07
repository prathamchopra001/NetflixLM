"""Smoke test of the running Compose stack (`docker compose up -d --wait`); skipped when it is down.

Everything is reached through the localhost-published ports; Postgres, object storage and the Ray
cluster are covered by the API's /readyz, which probes them over the Compose network.
"""

import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import pytest

pytestmark = pytest.mark.integration

API = "http://127.0.0.1:8000"
KEYCLOAK = "http://127.0.0.1:8180"


def _get(url: str, headers: dict[str, str] | None = None) -> tuple[int, Any]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            body = r.read()
            return r.status, json.loads(body) if body.startswith((b"{", b"[")) else body
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


@pytest.fixture(scope="module", autouse=True)
def stack_up() -> None:
    try:
        _get(f"{API}/healthz")
    except OSError:
        pytest.skip("Compose stack not running (docker compose up -d --wait)")


def test_every_service_is_healthy() -> None:
    out = subprocess.run(
        ["docker", "compose", "ps", "-a", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    rows = [json.loads(line) for line in out.splitlines() if line.strip()]
    status = {r["Service"]: (r["Health"] or r["State"], r["ExitCode"]) for r in rows}
    for name in ("postgres", "objectstore", "ray-head", "api", "keycloak", "mlflow"):
        assert status[name][0] == "healthy", status
    assert status["objectstore-init"] == ("exited", 0)


def test_readyz_reaches_postgres_object_storage_and_ray() -> None:
    assert _get(f"{API}/readyz") == (200, {"postgres": "ok", "object_storage": "ok", "ray": "ok"})


def test_keycloak_token_is_accepted_by_the_api() -> None:
    form = urllib.parse.urlencode(
        {"grant_type": "password", "client_id": "nip-ui", "username": "dev", "password": "dev"}
    ).encode()
    url = f"{KEYCLOAK}/realms/nip/protocol/openid-connect/token"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, form), timeout=10) as r:
            token = json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        pytest.skip(f"dev realm not imported (NIP_KEYCLOAK_DEV_REALM=true): HTTP {e.code}")
    status, me = _get(f"{API}/api/v1/me", {"Authorization": f"Bearer {token}"})
    assert status == 200
    assert {"viewer", "reviewer", "legal", "operator"} <= set(me["roles"])
    assert _get(f"{API}/api/v1/me")[0] == 401


def test_mlflow_and_ray_dashboard_answer() -> None:
    assert _get("http://127.0.0.1:5000/health")[0] == 200
    assert _get("http://127.0.0.1:8265/api/gcs_healthz")[0] == 200
