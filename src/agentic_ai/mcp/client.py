import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters


class MCPStatusClient:
    """MCP client adapter that launches the local tool server over stdio."""

    def __init__(self, module: str = "agentic_ai.mcp.server"):
        self.module = module

    async def get_incident_status(self, incident_id: str) -> dict[str, str]:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", self.module],
            env={"PYTHONPATH": str(Path(__file__).resolve().parents[3] / "src")},
        )
        async with Client(parameters) as client:
            result = await client.call_tool("get_incident_status", {"incident_id": incident_id})
        structured = result.structured_content
        if isinstance(structured, dict):
            return {str(key): str(value) for key, value in structured.items()}
        raise ValueError("MCP status tool returned no structured content")

    async def create_incident_ticket(
        self, title: str, description: str, idempotency_key: str
    ) -> dict[str, str]:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", self.module],
            env={"PYTHONPATH": str(Path(__file__).resolve().parents[3] / "src")},
        )
        async with Client(parameters) as client:
            result = await client.call_tool(
                "create_incident_ticket",
                {
                    "title": title,
                    "description": description,
                    "idempotency_key": idempotency_key,
                },
            )
        structured = result.structured_content
        if isinstance(structured, dict):
            return {str(key): str(value) for key, value in structured.items()}
        raise ValueError("MCP ticket tool returned no structured content")
