import pytest

from nip.store.db import database_url


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ("postgresql://nip:pw@postgres:5432/nip", "postgresql+psycopg://nip:pw@postgres:5432/nip"),
        ("postgresql+psycopg://nip@h/nip", "postgresql+psycopg://nip@h/nip"),
        (None, "postgresql+psycopg://"),
    ],
)
def test_database_url_uses_psycopg3(
    monkeypatch: pytest.MonkeyPatch, env: str | None, expected: str
) -> None:
    if env is None:
        monkeypatch.delenv("NIP_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("NIP_DATABASE_URL", env)
    assert database_url() == expected
