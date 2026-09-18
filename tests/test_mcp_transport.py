import pytest

from agentic_ai.mcp import MCPStatusClient


@pytest.mark.asyncio
async def test_local_mcp_stdio_transport_returns_structured_status() -> None:
    result = await MCPStatusClient().get_incident_status("INC-42")

    assert result["incident_id"] == "INC-42"
    assert result["status"] == "investigating"


@pytest.mark.asyncio
async def test_local_mcp_stdio_transport_creates_ticket() -> None:
    result = await MCPStatusClient().create_incident_ticket(
        "Database incident", "Replica lag exceeded threshold", "request-123456"
    )

    assert result["ticket_id"] == "TICKET-request-1234"
    assert result["status"] == "created"
