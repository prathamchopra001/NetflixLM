import time
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pydantic import BaseModel

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


def token(c: TestClient, drop: tuple[str, ...] = (), **over: Any) -> dict[str, str]:
    now = time.time()
    claims = {
        "sub": "u1",
        "iss": ISS,
        "aud": "nip-api",
        "iat": now,
        "exp": now + 60,
        "roles": ["reviewer"],
    } | over
    for k in drop:
        del claims[k]
    return {"Authorization": "Bearer " + jwt.encode(claims, c.key, "RS256")}  # type: ignore[attr-defined]


def assert_unauthorized(r: Any) -> None:
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_healthz_needs_no_auth(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/api/v1/healthz").status_code == 200


def test_me_returns_sub_and_roles(client: TestClient) -> None:
    r = client.get("/api/v1/me", headers=token(client))
    assert r.json() == {"sub": "u1", "roles": ["reviewer"]}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"iss": "http://evil/realms/nip"},
        {"aud": "other"},
        {"exp": 1},
        {"drop": ("exp",)},  # a token that never expires
        {"drop": ("sub",)},
        {"drop": ("iat",)},
        {"drop": ("aud",)},
        {"drop": ("iss",)},
        {"roles": "operator"},  # claim is not a list
        {"roles": [1]},
    ],
)
def test_me_rejects_bad_tokens_with_401(client: TestClient, kwargs: dict[str, Any]) -> None:
    assert_unauthorized(client.get("/api/v1/me", headers=token(client, **kwargs)))


def test_me_rejects_garbage_and_missing_token(client: TestClient) -> None:
    assert_unauthorized(client.get("/api/v1/me", headers={"Authorization": "Bearer not.a.jwt"}))
    assert_unauthorized(client.get("/api/v1/me"))


def test_signature_from_another_key_is_401(client: TestClient) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    claims = {"sub": "u", "iss": ISS, "aud": "nip-api", "iat": time.time(), "exp": time.time() + 60}
    bad = {"Authorization": "Bearer " + jwt.encode(claims, other, "RS256")}
    assert_unauthorized(client.get("/api/v1/me", headers=bad))


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
    want = {"postgres": "ok", "object_storage": "ok", "ray": "down: ConnectionError"}
    assert r.json() == {
        "error": {"code": "CLUSTER_UNAVAILABLE", "message": "Not ready: ray", "details": want}
    }


def test_unknown_route_and_validation_use_the_envelope(client: TestClient) -> None:
    r = client.get("/api/v1/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"

    class Body(BaseModel):
        n: int

    def echo(body: Body) -> Body:
        return body

    client.app.add_api_route("/echo2", echo, methods=["POST"])  # type: ignore[attr-defined]
    r = client.post("/echo2", json={"n": "x"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_FAILED"
    assert r.json()["error"]["details"]
