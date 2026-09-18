import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from agentic_ai.observability import LangfuseObservability


class MCPStatusClient:
    """MCP client adapter that launches the local tool server over stdio."""

    def __init__(
        self,
        module: str = "agentic_ai.mcp.server",
        observability: LangfuseObservability | None = None,
    ):
        self.module = module
        self.observability = observability

    async def get_incident_status(self, incident_id: str) -> dict[str, str]:
        async def call_tool() -> dict[str, str]:
            async with Client(self._parameters()) as client:
                result = await client.call_tool("get_incident_status", {"incident_id": incident_id})
            structured = result.structured_content
            if isinstance(structured, dict):
                return {str(key): str(value) for key, value in structured.items()}
            raise ValueError("MCP status tool returned no structured content")

        if not self.observability:
            return await call_tool()
        return await self.observability.observe(
            name="mcp.get_incident_status",
            as_type="tool",
            operation=call_tool,
            metadata={"tool_name": "get_incident_status"},
            output_builder=lambda result: {"status": result.get("status")},
        )

    async def create_incident_ticket(
        self, title: str, description: str, idempotency_key: str
    ) -> dict[str, str]:
        async def call_tool() -> dict[str, str]:
            async with Client(self._parameters()) as client:
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

        if not self.observability:
            return await call_tool()
        return await self.observability.observe(
            name="mcp.create_incident_ticket",
            as_type="tool",
            operation=call_tool,
            metadata={"tool_name": "create_incident_ticket"},
            output_builder=lambda result: {
                "status": result.get("status"),
                "ticket_id": result.get("ticket_id"),
            },
        )

    def _parameters(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", self.module],
            env={"PYTHONPATH": str(Path(__file__).resolve().parents[3] / "src")},
        )
