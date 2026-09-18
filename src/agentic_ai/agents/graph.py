from collections.abc import Awaitable, Callable
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agentic_ai.retrieval.contracts import AccessContext, Retriever, SearchResult


class AgentState(TypedDict, total=False):
    query: str
    access: AccessContext
    evidence: list[SearchResult]
    live_status: dict[str, str]
    needs_investigation: bool
    answer: str
    citations: list[str]


StatusTool = Callable[[str], Awaitable[dict[str, str]]]


def build_agent_graph(retriever: Retriever, status_tool: StatusTool | None = None):
    """Build a bounded incident workflow with explicit, testable transitions."""

    async def retrieve(state: AgentState) -> dict[str, object]:
        evidence = await retriever.search(state["query"], state["access"], limit=5)
        return {"evidence": evidence}

    def decide_investigation(state: AgentState) -> dict[str, bool]:
        query = state["query"].lower()
        live_terms = ("current", "now", "live", "status", "ongoing")
        return {"needs_investigation": bool(status_tool and any(term in query for term in live_terms))}

    async def investigate(state: AgentState) -> dict[str, object]:
        if not status_tool:
            return {"live_status": {"status": "unavailable"}}
        incident_id = state["query"].split()[-1].strip(".,?!")
        return {"live_status": await status_tool(incident_id)}

    def compose(state: AgentState) -> dict[str, object]:
        evidence = state.get("evidence", [])
        citations = list(dict.fromkeys(result.source for result in evidence))
        if not evidence:
            return {
                "answer": "I could not find sufficient authorized evidence to answer this reliably.",
                "citations": [],
            }
        answer = evidence[0].text
        if state.get("live_status"):
            answer = f"{answer}\n\nLive status: {state['live_status']}"
        return {"answer": answer, "citations": citations}

    def route(state: AgentState) -> str:
        return "investigate" if state.get("needs_investigation") else "compose"

    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("decide_investigation", decide_investigation)
    graph.add_node("investigate", investigate)
    graph.add_node("compose", compose)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "decide_investigation")
    graph.add_conditional_edges(
        "decide_investigation", route, {"investigate": "investigate", "compose": "compose"}
    )
    graph.add_edge("investigate", "compose")
    graph.add_edge("compose", END)
    return graph.compile()
