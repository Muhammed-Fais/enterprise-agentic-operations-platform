from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Header, HTTPException, status

from agentic_ai.config import get_settings


@dataclass(frozen=True)
class AuthContext:
    tenant_id: str
    subject_id: str
    roles: tuple[str, ...]


def get_auth_context(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[get_settings().jwt_algorithm],
            options={"require": ["sub", "tenant_id"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token"
        ) from exc

    roles = claims.get("roles", [])
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid roles claim")
    return AuthContext(
        tenant_id=str(claims["tenant_id"]),
        subject_id=str(claims["sub"]),
        roles=tuple(roles),
    )
