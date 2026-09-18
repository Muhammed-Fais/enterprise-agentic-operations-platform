from pathlib import Path

import pytest

from agentic_ai.ingestion import load_file


def test_load_markdown(tmp_path: Path) -> None:
    path = tmp_path / "policy.md"
    path.write_text("# Access policy\n\nManagers need approval.", encoding="utf-8")

    document = load_file(path)

    assert document.title == "policy"
    assert "Managers need approval" in document.content


def test_rejects_unknown_file_type(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("a,b", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported document type"):
        load_file(path)
