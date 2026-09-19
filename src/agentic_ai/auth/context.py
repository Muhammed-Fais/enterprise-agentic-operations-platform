from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Header, HTTPException, status
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError

from agentic_ai.config import get_settings


@dataclass(frozen=True)
class AuthContext:
    tenant_id: str
    subject_id: str
    roles: tuple[str, ...]


@lru_cache(maxsize=8)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_jwk_set=True, lifespan=300)


def get_auth_context(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")

    token = authorization.removeprefix("Bearer ").strip()
    settings = get_settings()
    try:
        key = settings.jwt_secret
        if settings.jwt_jwks_url:
            key = _jwks_client(settings.jwt_jwks_url).get_signing_key_from_jwt(token).key
        decode_options: dict[str, object] = {"require": ["sub", "tenant_id"]}
        decode_kwargs: dict[str, object] = {
            "key": key,
            "algorithms": [settings.jwt_algorithm],
            "options": decode_options,
        }
        if settings.jwt_issuer:
            decode_kwargs["issuer"] = settings.jwt_issuer
        if settings.jwt_audience:
            decode_kwargs["audience"] = settings.jwt_audience
        claims = jwt.decode(token, **decode_kwargs)
    except (jwt.PyJWTError, PyJWKClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token"
        ) from exc

    roles = claims.get("roles", [])
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid roles claim")
    tenant_id = claims["tenant_id"]
    subject_id = claims["sub"]
    if not isinstance(tenant_id, str) or not tenant_id.strip() or not isinstance(subject_id, str) or not subject_id.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid identity claims")
    return AuthContext(
        tenant_id=tenant_id,
        subject_id=subject_id,
        roles=tuple(roles),
    )
