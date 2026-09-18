import pytest

from agentic_ai.agents import build_agent_graph
from agentic_ai.auth import AuthContext
from agentic_ai.retrieval.contracts import SearchResult


class FakeRetriever:
    async def search(self, query, access, *, limit=5):
        return [
            SearchResult("chunk-1", "doc-1", "Check replica health.", 0.9, "runbook.md", {})
        ]


@pytest.mark.asyncio
async def test_graph_retrieves_and_investigates_live_status() -> None:
    async def status_tool(incident_id: str) -> dict[str, str]:
        return {"incident_id": incident_id, "status": "investigating"}

    graph = build_agent_graph(FakeRetriever(), status_tool)
    result = await graph.ainvoke(
        {
            "query": "What is the current status INC-42?",
            "access": AuthContext("tenant-a", "user-1", ("analyst",)),
        }
    )

    assert "Check replica health." in result["answer"]
    assert "investigating" in result["answer"]
    assert result["citations"] == ["runbook.md"]


@pytest.mark.asyncio
async def test_graph_abstains_without_evidence() -> None:
    class EmptyRetriever:
        async def search(self, query, access, *, limit=5):
            return []

    graph = build_agent_graph(EmptyRetriever())
    result = await graph.ainvoke(
        {"query": "What is the policy?", "access": AuthContext("tenant-a", "user-1", ())}
    )

    assert "sufficient authorized evidence" in result["answer"]
