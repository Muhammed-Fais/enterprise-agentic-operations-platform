import json
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agentic_ai.auth import AuthContext


async def record_event(
    session: AsyncSession,
    context: AuthContext,
    request_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Persist a structured security/business event without storing raw sensitive inputs."""
    await session.execute(
        text(
            """
            INSERT INTO audit_events (id, tenant_id, subject_id, event_type, request_id, payload)
            VALUES (:id, :tenant_id, :subject_id, :event_type, :request_id, CAST(:payload AS jsonb))
            """
        ),
        {
            "id": uuid4(),
            "tenant_id": context.tenant_id,
            "subject_id": context.subject_id,
            "event_type": event_type,
            "request_id": request_id,
            "payload": json.dumps(payload or {}),
        },
    )
    await session.commit()
