import pytest

from agentic_ai.auth import AuthContext
from agentic_ai.mcp import ApprovalRequired, ToolAuthorization, ToolCapability, ToolPolicy


def _authorization() -> ToolAuthorization:
    return ToolAuthorization(
        [
            ToolPolicy("get_incident_status", ToolCapability.READ_ONLY, frozenset({"analyst"})),
            ToolPolicy("create_ticket", ToolCapability.WRITE, frozenset({"analyst"})),
        ]
    )


def test_read_tool_requires_role_but_not_approval() -> None:
    authorization = _authorization()
    context = AuthContext("tenant-a", "user-1", ("analyst",))

    authorization.authorize(context, "get_incident_status", {"incident_id": "INC-1"})


def test_write_tool_requires_matching_human_approval() -> None:
    authorization = _authorization()
    context = AuthContext("tenant-a", "user-1", ("analyst",))
    arguments = {"title": "Database incident"}

    with pytest.raises(ApprovalRequired) as error:
        authorization.authorize(context, "create_ticket", arguments)

    authorization.authorize(
        context,
        "create_ticket",
        arguments,
        approval_token=error.value.approval_token,
        idempotency_key="request-1",
    )


def test_approval_cannot_be_reused_for_different_arguments() -> None:
    authorization = _authorization()
    context = AuthContext("tenant-a", "user-1", ("analyst",))
    with pytest.raises(ApprovalRequired) as error:
        authorization.authorize(context, "create_ticket", {"title": "Original"})

    with pytest.raises(PermissionError):
        authorization.authorize(
            context,
            "create_ticket",
            {"title": "Tampered"},
            approval_token=error.value.approval_token,
        )
