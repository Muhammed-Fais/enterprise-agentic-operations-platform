import pytest

from agentic_ai.mcp import MCPStatusClient


@pytest.mark.asyncio
async def test_local_mcp_stdio_transport_returns_structured_status() -> None:
    result = await MCPStatusClient().get_incident_status("INC-42")

    assert result["incident_id"] == "INC-42"
    assert result["status"] == "investigating"
