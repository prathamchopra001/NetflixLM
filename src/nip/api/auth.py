"""OIDC bearer-token auth (docs/api-contracts.md Conventions, D-019).

The expected issuer and the key-fetch URL are separate settings: browsers reach Keycloak at
localhost:8180 (so tokens carry that issuer) while this container can only reach keycloak:8080.
"""

import os
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


@lru_cache
def _jwks() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(os.environ["NIP_OIDC_JWKS_URL"], cache_keys=True)


def _claims(creds: HTTPAuthorizationCredentials | None) -> dict[str, Any]:
    if creds is None:
        raise HTTPException(401, "missing bearer token", {"WWW-Authenticate": "Bearer"})
    try:
        key = _jwks().get_signing_key_from_jwt(creds.credentials)
        return jwt.decode(
            creds.credentials,
            key.key,
            algorithms=["RS256", "ES256"],
            issuer=os.environ["NIP_OIDC_ISSUER"],
            audience=os.environ.get("NIP_OIDC_AUDIENCE", "nip-api"),
        )
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"invalid token: {e}", {"WWW-Authenticate": "Bearer"}) from e


def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict[str, Any]:
    claims = _claims(creds)
    roles = claims.get(os.environ.get("NIP_OIDC_ROLES_CLAIM", "roles"), [])
    return {"sub": claims["sub"], "roles": sorted(roles if isinstance(roles, list) else [roles])}
