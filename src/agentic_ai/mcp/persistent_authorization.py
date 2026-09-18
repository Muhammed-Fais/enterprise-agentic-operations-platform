import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agentic_ai.auth import AuthContext

from .authorization import ToolCapability, ToolPolicy


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _arguments_hash(arguments: dict[str, object]) -> str:
    encoded = json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode()
    return _hash(encoded.decode())


class PersistentToolAuthorization:
    def __init__(self, policies: list[ToolPolicy]):
        self._policies = {policy.name: policy for policy in policies}

    def _policy(self, context: AuthContext, tool_name: str) -> ToolPolicy:
        policy = self._policies.get(tool_name)
        if not policy or not (policy.allowed_roles & set(context.roles)):
            raise PermissionError("tool is not authorized for this role")
        return policy

    async def request_approval(
        self, session: AsyncSession, context: AuthContext, tool_name: str, arguments: dict[str, object]
    ) -> str:
        policy = self._policy(context, tool_name)
        if policy.capability is not ToolCapability.WRITE:
            raise PermissionError("approval is only available for write tools")
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(minutes=5)
        await session.execute(
            text(
                """
                INSERT INTO tool_approvals
                    (id, token_hash, tenant_id, subject_id, tool_name, arguments_hash, status, expires_at)
                VALUES (:id, :token_hash, :tenant_id, :subject_id, :tool_name, :arguments_hash,
                        'pending', :expires_at)
                """
            ),
            {
                "id": uuid4(),
                "token_hash": _hash(token),
                "tenant_id": context.tenant_id,
                "subject_id": context.subject_id,
                "tool_name": tool_name,
                "arguments_hash": _arguments_hash(arguments),
                "expires_at": expires_at,
            },
        )
        await session.commit()
        return token

    async def get_idempotent_result(
        self,
        session: AsyncSession,
        context: AuthContext,
        tool_name: str,
        arguments: dict[str, object],
        idempotency_key: str,
    ) -> dict[str, str] | None:
        row = (
            await session.execute(
                text(
                    """
                    SELECT arguments_hash, status, result
                    FROM idempotency_records
                    WHERE tenant_id = :tenant_id AND idempotency_key = :idempotency_key
                    """
                ),
                {"tenant_id": context.tenant_id, "idempotency_key": idempotency_key},
            )
        ).mappings().first()
        if not row:
            return None
        if row["arguments_hash"] != _arguments_hash(arguments):
            raise PermissionError("idempotency key is already bound to another action")
        if row["status"] == "in_progress":
            raise PermissionError("idempotency key is already in progress")
        if row["status"] != "completed":
            raise PermissionError("idempotency key cannot be reused after failure")
        return row["result"] or {}

    async def authorize(
        self,
        session: AsyncSession,
        context: AuthContext,
        tool_name: str,
        arguments: dict[str, object],
        approval_token: str,
        idempotency_key: str,
    ) -> None:
        policy = self._policy(context, tool_name)
        if policy.capability is not ToolCapability.WRITE:
            raise PermissionError("tool is not a write action")
        arguments_hash = _arguments_hash(arguments)
        existing = (
            await session.execute(
                text(
                    """
                    SELECT tool_name, arguments_hash, status
                    FROM idempotency_records
                    WHERE tenant_id = :tenant_id AND idempotency_key = :idempotency_key
                    FOR UPDATE
                    """
                ),
                {"tenant_id": context.tenant_id, "idempotency_key": idempotency_key},
            )
        ).mappings().first()
        if existing:
            await session.rollback()
            if existing["tool_name"] != tool_name or existing["arguments_hash"] != arguments_hash:
                raise PermissionError("idempotency key is already bound to another action")
            raise PermissionError("idempotency key is already in progress or completed")
        row = (
            await session.execute(
                text(
                    """
                    SELECT status, tenant_id, subject_id, tool_name, arguments_hash, expires_at
                    FROM tool_approvals
                    WHERE token_hash = :token_hash
                    FOR UPDATE
                    """
                ),
                {"token_hash": _hash(approval_token)},
            )
        ).mappings().first()
        now = datetime.now(UTC)
        if (
            not row
            or row["status"] != "pending"
            or row["expires_at"] <= now
            or row["tenant_id"] != context.tenant_id
            or row["subject_id"] != context.subject_id
            or row["tool_name"] != tool_name
            or row["arguments_hash"] != arguments_hash
        ):
            await session.rollback()
            raise PermissionError("approval is missing, expired, consumed, or does not match")
        await session.execute(
            text(
                "UPDATE tool_approvals SET status = 'consumed', consumed_at = now() "
                "WHERE token_hash = :token_hash"
            ),
            {"token_hash": _hash(approval_token)},
        )
        await session.execute(
            text(
                """
                INSERT INTO idempotency_records
                    (tenant_id, idempotency_key, tool_name, arguments_hash, status)
                VALUES (:tenant_id, :idempotency_key, :tool_name, :arguments_hash, 'in_progress')
                ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
                """
            ),
            {
                "tenant_id": context.tenant_id,
                "idempotency_key": idempotency_key,
                "tool_name": tool_name,
                "arguments_hash": arguments_hash,
            },
        )
        await session.commit()

    async def fail(
        self,
        session: AsyncSession,
        context: AuthContext,
        idempotency_key: str,
        error: str,
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE idempotency_records
                SET status = 'failed', result = CAST(:result AS jsonb), completed_at = now()
                WHERE tenant_id = :tenant_id AND idempotency_key = :idempotency_key
                """
            ),
            {
                "tenant_id": context.tenant_id,
                "idempotency_key": idempotency_key,
                "result": json.dumps({"error": error}),
            },
        )
        await session.commit()

    async def complete(
        self,
        session: AsyncSession,
        context: AuthContext,
        idempotency_key: str,
        result: dict[str, str],
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE idempotency_records
                SET status = 'completed', result = CAST(:result AS jsonb), completed_at = now()
                WHERE tenant_id = :tenant_id AND idempotency_key = :idempotency_key
                """
            ),
            {
                "tenant_id": context.tenant_id,
                "idempotency_key": idempotency_key,
                "result": json.dumps(result),
            },
        )
        await session.commit()
