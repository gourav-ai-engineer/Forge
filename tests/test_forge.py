from __future__ import annotations

from pathlib import Path

import pytest

from forge.engine import ForgeEngine
from forge.github import parse_issue_url
from forge.planner import JSONPlanner
from forge.sandbox import SandboxRunner
from forge.types import ForgeTask, RunStatus, ToolCall
from forge.workspace import Workspace


def test_workspace_blocks_path_escape(tmp_path: Path) -> None:
    ws = Workspace(tmp_path)
    with pytest.raises(ValueError):
        ws.path("../outside.txt")


def test_write_requires_explicit_approval(tmp_path: Path) -> None:
    from forge.tools import ToolRegistry

    registry = ToolRegistry(Workspace(tmp_path), allow_writes=False)
    result = registry.execute(ToolCall("write_file", {"path": "x.txt", "content": "secret"}))
    assert not result.ok
    assert not (tmp_path / "x.txt").exists()


def test_offline_engine_smoke(tmp_path: Path) -> None:
    (tmp_path / "test_sample.py").write_text("def test_ok(): assert 1 + 1 == 2\n", encoding="utf-8")
    report = ForgeEngine().run(ForgeTask("inspect", str(tmp_path)))
    assert report.status is RunStatus.SUCCEEDED
    assert {step.tool for step in report.steps} == {
        "repo_analyze", "repo_tree", "git_status", "run_tests"
    }


def test_planner_json_validation() -> None:
    planner = JSONPlanner()
    calls = planner.parse('{"steps":[{"tool":"repo_tree","arguments":{},"reason":"inspect"}]}')
    assert calls == (ToolCall("repo_tree", {}, "inspect"),)


def test_unknown_tool_fails(tmp_path: Path) -> None:
    from forge.tools import ToolRegistry

    result = ToolRegistry(Workspace(tmp_path)).execute(ToolCall("nope"))
    assert not result.ok


def test_sandbox_reports_missing_docker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("forge.sandbox.shutil.which", lambda _: None)
    result = SandboxRunner(tmp_path).run(["python", "-m", "pytest", "-q"])
    assert not result.ok
    assert "Docker CLI not found" in result.error


def test_github_issue_url_parser() -> None:
    assert parse_issue_url("https://github.com/acme/project/issues/42") == ("acme", "project", 42)
    with pytest.raises(ValueError):
        parse_issue_url("https://example.com/acme/project/issues/42")
