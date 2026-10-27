from __future__ import annotations

import json
from pathlib import Path

from forge.retrieval import CodeRetriever
from forge.tools import ToolRegistry
from forge.types import ToolCall
from forge.workspace import Workspace


def test_bm25_retrieves_relevant_source_and_line_numbers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FORGE_USE_CHROMA", "0")
    (tmp_path / "github_issue.py").write_text(
        "def parse_github_issue_url(url):\n"
        "    # Parse issue URL and extract owner, repository and number.\n"
        "    return url.split('/')\n",
        encoding="utf-8",
    )
    (tmp_path / "email_utils.py").write_text(
        "def normalize_email(value):\n"
        "    return value.strip().lower()\n",
        encoding="utf-8",
    )

    results = CodeRetriever(tmp_path).search("parse GitHub issue URL repository", limit=5)

    assert results
    assert results[0]["path"] == "github_issue.py"
    assert results[0]["start_line"] == 1
    assert "parse_github_issue_url" in results[0]["text"]


def test_retriever_ignores_environment_secrets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FORGE_USE_CHROMA", "0")
    (tmp_path / "app.py").write_text("def ask_model(): return True\n", encoding="utf-8")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=never-index-this-secret\n", encoding="utf-8")

    results = CodeRetriever(tmp_path).search("OPENAI API key ask model", limit=10)

    assert all(item["path"] != ".env" for item in results)
    assert all("never-index-this-secret" not in item["text"] for item in results)


def test_search_code_tool_returns_json_payload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FORGE_USE_CHROMA", "0")
    (tmp_path / "workspace.py").write_text("def inspect_workspace(): return []\n", encoding="utf-8")
    registry = ToolRegistry(Workspace(tmp_path))

    result = registry.execute(ToolCall("search_code", {"query": "inspect workspace", "limit": 3}))

    assert result.ok
    payload = json.loads(result.output)
    assert payload["retrieval_mode"] == "bm25"
    assert payload["count"] >= 1
    assert payload["results"][0]["path"] == "workspace.py"
