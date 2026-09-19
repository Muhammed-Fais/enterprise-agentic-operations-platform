from agentic_ai.evaluation import SecurityCase, evaluate_security_dataset, load_security_cases


def test_security_dataset_passes() -> None:
    report = evaluate_security_dataset(
        load_security_cases("data/evaluation/security_cases.jsonl")
    )

    assert report.passed
    assert report.cases_evaluated == 8
    assert report.failed_cases == 0
    assert report.by_category == {
        "pii": 2,
        "prompt_injection": 3,
        "acl": 1,
        "tool_authorization": 2,
    }


def test_security_dataset_fails_on_cross_tenant_leak() -> None:
    case = SecurityCase(
        "acl-leak",
        "acl",
        {
            "retrieved_chunk_ids": ["tenant-b-secret"],
            "forbidden_chunk_ids": ["tenant-b-secret"],
        },
    )

    report = evaluate_security_dataset([case])

    assert not report.passed
    assert report.failed_cases == 1
    assert "forbidden chunks returned" in report.failures[0]
