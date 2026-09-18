from agentic_ai.retrieval.contracts import AccessContext, SearchResult


def test_access_context_and_search_result_are_typed_boundaries() -> None:
    access = AccessContext(tenant_id="tenant-a", subject_id="user-1", roles=("analyst",))
    result = SearchResult(
        chunk_id="chunk-1",
        document_id="doc-1",
        text="Database incident response",
        score=0.91,
        source="incident.md",
        metadata={"title": "Incident"},
    )

    assert access.tenant_id == "tenant-a"
    assert result.score == 0.91
