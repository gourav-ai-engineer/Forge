from __future__ import annotations

from forge.github_pr import create_pull_request
from forge.workspace import Workspace
import pytest


def test_pr_publication_requires_token_before_any_network_call(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
        create_pull_request(
            Workspace(tmp_path),
            title="Test PR",
            body="Test",
            expected_head_sha="abc123",
            task_id="unit-test",
            tests_passed_in_sandbox=True,
        )


def test_pr_publication_requires_sandbox_validation(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    with pytest.raises(RuntimeError, match="sandboxed test validation"):
        create_pull_request(
            Workspace(tmp_path),
            title="Test PR",
            body="Test",
            expected_head_sha="abc123",
            task_id="unit-test",
            tests_passed_in_sandbox=False,
        )
