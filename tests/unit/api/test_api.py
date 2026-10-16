import time
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from nip.api import app as app_mod
from nip.api import auth
from nip.api.app import create_app

ISS = "http://localhost:8180/realms/nip"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NIP_OIDC_ISSUER", ISS)
    monkeypatch.setenv("NIP_OIDC_AUDIENCE", "nip-api")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(
        auth,
        "_jwks",
        lambda: SimpleNamespace(
            get_signing_key_from_jwt=lambda _t: SimpleNamespace(key=key.public_key())
        ),
    )
    c = TestClient(create_app())
    c.key = key  # type: ignore[attr-defined]
    return c


def token(c: TestClient, **over: Any) -> dict[str, str]:
    claims = {
        "sub": "u1",
        "iss": ISS,
        "aud": "nip-api",
        "exp": time.time() + 60,
        "roles": ["reviewer"],
    } | over
    return {"Authorization": "Bearer " + jwt.encode(claims, c.key, "RS256")}  # type: ignore[attr-defined]


def test_healthz_needs_no_auth(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/api/v1/healthz").status_code == 200


def test_me_returns_sub_and_roles(client: TestClient) -> None:
    r = client.get("/api/v1/me", headers=token(client))
    assert r.json() == {"sub": "u1", "roles": ["reviewer"]}


@pytest.mark.parametrize("over", [{"iss": "http://evil/realms/nip"}, {"aud": "other"}, {"exp": 1}])
def test_me_rejects_bad_tokens(client: TestClient, over: dict[str, Any]) -> None:
    assert client.get("/api/v1/me", headers=token(client, **over)).status_code == 401


def test_me_without_token_is_401(client: TestClient) -> None:
    assert client.get("/api/v1/me").status_code == 401


def test_readyz_names_the_failing_dependency(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("_postgres", "_object_storage", "_ray"):
        monkeypatch.setattr(app_mod, name, lambda: None)
    assert client.get("/readyz").json() == {"postgres": "ok", "object_storage": "ok", "ray": "ok"}

    def boom() -> None:
        raise ConnectionError("x")

    monkeypatch.setattr(app_mod, "_ray", boom)
    r = client.get("/readyz")
    assert r.status_code == 503
    assert r.json()["detail"] == {
        "postgres": "ok",
        "object_storage": "ok",
        "ray": "down: ConnectionError",
    }
