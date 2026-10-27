from __future__ import annotations

import sys
import types

from forge.providers import OpenAIPlanner, provider_from_env
from forge.types import ForgeTask


def test_provider_from_env_selects_luna(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("FORGE_MODEL", raising=False)
    planner = provider_from_env()
    assert isinstance(planner, OpenAIPlanner)
    assert planner.model == "gpt-5.6-luna"


def test_openai_planner_parses_responses_output(monkeypatch) -> None:
    calls = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return types.SimpleNamespace(
                output_text='{"steps":[{"tool":"repo_tree","arguments":{},"reason":"inspect"}],"summary":"done"}'
            )

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["api_key"] == "test-key"
            self.responses = FakeResponses()

    fake_openai = types.SimpleNamespace(OpenAI=FakeClient)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    planner = OpenAIPlanner()
    result = planner.plan(
        ForgeTask(request="Inspect the repository", repo_path="."),
        "repo_tree: OK\nREADME.md",
    )

    assert result[0].name == "repo_tree"
    assert calls[0]["model"] == "gpt-5.6-luna"
    assert "Inspect the repository" in calls[0]["input"]
