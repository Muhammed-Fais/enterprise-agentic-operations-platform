import jwt
import pytest
from fastapi import HTTPException

from agentic_ai.auth import get_auth_context
from agentic_ai.config import get_settings


def test_auth_context_is_derived_from_signed_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-secret-with-at-least-32-bytes-long")
    get_settings.cache_clear()
    token = jwt.encode(
        {"sub": "user-1", "tenant_id": "tenant-a", "roles": ["analyst"]},
        "test-secret-with-at-least-32-bytes-long",
        algorithm="HS256",
    )

    context = get_auth_context(f"Bearer {token}")

    assert context.tenant_id == "tenant-a"
    assert context.subject_id == "user-1"
    assert context.roles == ("analyst",)
    get_settings.cache_clear()


def test_auth_context_rejects_missing_token() -> None:
    with pytest.raises(HTTPException) as error:
        get_auth_context(None)

    assert error.value.status_code == 401
