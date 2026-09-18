from mcp.server import MCPServer

mcp = MCPServer("enterprise-operations-tools")


@mcp.tool()
def get_incident_status(incident_id: str) -> dict[str, str]:
    """Return a read-only status snapshot for an incident."""
    return {
        "incident_id": incident_id,
        "status": "investigating",
        "severity": "medium",
        "source": "demo-status-system",
    }


@mcp.tool()
def draft_incident_ticket(title: str, description: str) -> dict[str, str]:
    """Draft a ticket payload; creating the ticket requires the application approval gate."""
    return {"title": title, "description": description, "status": "draft"}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
