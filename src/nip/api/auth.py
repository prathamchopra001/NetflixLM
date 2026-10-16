"""OIDC bearer-token auth (docs/api-contracts.md Conventions, D-019).

The expected issuer and the key-fetch URL are separate settings: browsers reach Keycloak at
localhost:8180 (so tokens carry that issuer) while this container can only reach keycloak:8080.
"""

import os
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from nip.api.errors import ApiError

_bearer = HTTPBearer(auto_error=False)
_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def _unauthorized(message: str) -> ApiError:
    return ApiError(401, "UNAUTHORIZED", message, headers=_CHALLENGE)


@lru_cache
def _jwks() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(os.environ["NIP_OIDC_JWKS_URL"], cache_keys=True)


def _claims(creds: HTTPAuthorizationCredentials | None) -> dict[str, Any]:
    if creds is None:
        raise _unauthorized("Missing bearer token")
    try:
        key = _jwks().get_signing_key_from_jwt(creds.credentials)
        return jwt.decode(
            creds.credentials,
            key.key,
            algorithms=["RS256", "ES256"],
            issuer=os.environ["NIP_OIDC_ISSUER"],
            audience=os.environ.get("NIP_OIDC_AUDIENCE", "nip-api"),
            # A token that never expires, or has no subject, is not accepted.
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as e:
        raise _unauthorized(f"Invalid token: {type(e).__name__}") from e


def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict[str, Any]:
    claims = _claims(creds)
    roles = claims.get(os.environ.get("NIP_OIDC_ROLES_CLAIM", "roles"), [])
    if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
        raise _unauthorized("Invalid token: roles claim must be a list of strings")
    return {"sub": claims["sub"], "roles": sorted(roles)}
