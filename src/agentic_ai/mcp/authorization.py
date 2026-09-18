import hashlib
import json
import secrets
from dataclasses import dataclass
from enum import StrEnum
from time import time

from agentic_ai.auth import AuthContext


class ToolCapability(StrEnum):
    READ_ONLY = "read_only"
    WRITE = "write"


@dataclass(frozen=True)
class ToolPolicy:
    name: str
    capability: ToolCapability
    allowed_roles: frozenset[str]


class ApprovalRequired(Exception):
    def __init__(self, approval_token: str):
        super().__init__("human approval required")
        self.approval_token = approval_token


@dataclass(frozen=True)
class _Approval:
    token: str
    tenant_id: str
    subject_id: str
    tool_name: str
    arguments_hash: str
    expires_at: float


def _arguments_hash(arguments: dict[str, object]) -> str:
    encoded = json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class ToolAuthorization:
    """Application-side tool authorization; MCP annotations are not security."""

    def __init__(self, policies: list[ToolPolicy]):
        self._policies = {policy.name: policy for policy in policies}
        self._approvals: dict[str, _Approval] = {}
        self._completed_idempotency_keys: set[str] = set()

    def authorize(
        self,
        context: AuthContext,
        tool_name: str,
        arguments: dict[str, object],
        *,
        approval_token: str | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        policy = self._policies.get(tool_name)
        if not policy or not (policy.allowed_roles & set(context.roles)):
            raise PermissionError("tool is not authorized for this role")
        if idempotency_key and idempotency_key in self._completed_idempotency_keys:
            return
        if policy.capability is ToolCapability.READ_ONLY:
            return
        if not approval_token:
            token = self.request_approval(context, tool_name, arguments)
            raise ApprovalRequired(token)
        approval = self._approvals.get(approval_token)
        if not approval or approval.expires_at < time():
            raise PermissionError("approval is missing or expired")
        if (
            approval.tenant_id != context.tenant_id
            or approval.subject_id != context.subject_id
            or approval.tool_name != tool_name
            or approval.arguments_hash != _arguments_hash(arguments)
        ):
            raise PermissionError("approval does not match this tool call")
        if idempotency_key:
            self._completed_idempotency_keys.add(idempotency_key)

    def request_approval(
        self, context: AuthContext, tool_name: str, arguments: dict[str, object]
    ) -> str:
        policy = self._policies.get(tool_name)
        if not policy or policy.capability is not ToolCapability.WRITE:
            raise PermissionError("approval is only available for write tools")
        if not (policy.allowed_roles & set(context.roles)):
            raise PermissionError("tool is not authorized for this role")
        token = secrets.token_urlsafe(24)
        self._approvals[token] = _Approval(
            token=token,
            tenant_id=context.tenant_id,
            subject_id=context.subject_id,
            tool_name=tool_name,
            arguments_hash=_arguments_hash(arguments),
            expires_at=time() + 300,
        )
        return token
