from __future__ import annotations

from pathlib import Path

import pytest

from forge.workspace import Workspace


def test_secret_file_is_not_listed_or_read(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("OPENAI_API_KEY=do-not-index", encoding="utf-8")
    (tmp_path / "visible.py").write_text("def visible(): return True\n", encoding="utf-8")
    workspace = Workspace(tmp_path)

    assert "visible.py" in workspace.list_files()
    assert ".env" not in workspace.list_files()
    with pytest.raises(ValueError, match="protected"):
        workspace.read(".env")


def test_workflow_files_cannot_be_mutated_by_agent(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: safe\n", encoding="utf-8")

    with pytest.raises(ValueError, match="writes to GitHub automation"):
        Workspace(tmp_path).write(".github/workflows/ci.yml", "name: changed\n", allow_write=True)


def test_symlink_path_is_rejected(tmp_path: Path) -> None:
    secret = tmp_path / "private.py"
    secret.write_text("do_not_read = True\n", encoding="utf-8")
    link = tmp_path / "linked.py"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this platform")

    with pytest.raises(ValueError, match="symbolic links"):
        Workspace(tmp_path).read("linked.py")


def test_child_process_does_not_inherit_model_or_github_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "fake-github-secret")
    result = Workspace(tmp_path).run([
        "python", "-c",
        "import os; print(os.getenv('OPENAI_API_KEY', 'MISSING')); print(os.getenv('GITHUB_TOKEN', 'MISSING'))",
    ])

    assert result.ok
    assert "fake-openai-secret" not in result.output
    assert "fake-github-secret" not in result.output
    assert result.output.splitlines() == ["MISSING", "MISSING"]
