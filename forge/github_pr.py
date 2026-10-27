from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

import requests

from .workspace import Workspace

API_URL = "https://api.github.com"
REMOTE_RE = re.compile(r"(?:https://github\.com/|git@github\.com:)([^/\s]+)/([^/\s]+?)(?:\.git)?$")
PROTECTED_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
PROTECTED_NAMES = {".env", "id_rsa", "id_ed25519", "credentials.json"}
PROTECTED_DIRS = {".git", ".ssh", ".aws", ".kube", ".forge"}


def _request(method: str, url: str, token: str, **kwargs: Any) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Forge-Autonomous-Engineer",
    }
    response = requests.request(method, url, headers=headers, timeout=20, **kwargs)
    if not response.ok:
        message = f"GitHub API request failed with HTTP {response.status_code}"
        try:
            detail = response.json().get("message")
            if detail:
                message += f": {detail}"
        except (ValueError, AttributeError):
            pass
        raise RuntimeError(message)
    return response.json() if response.content else {}


def _blocked(path: str) -> bool:
    parts = Path(path).parts
    lowered = [part.casefold() for part in parts]
    name = Path(path).name.casefold()
    if any(part in PROTECTED_DIRS for part in lowered):
        return True
    if name in PROTECTED_NAMES or name.endswith(tuple(PROTECTED_SUFFIXES)):
        return True
    if name.startswith(".env.") and name != ".env.example":
        return True
    if "secrets" in name or "credentials" in name:
        return True
    if lowered[:2] == [".github", "workflows"] or lowered[:2] == [".github", "actions"]:
        return True
    return False


def create_pull_request(
    workspace: Workspace,
    *,
    title: str,
    body: str,
    expected_head_sha: str,
    task_id: str,
    tests_passed_in_sandbox: bool,
    base_branch: str | None = None,
) -> dict[str, Any]:
    """Publish an unmerged PR for validated changes using GitHub's Git Data API."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required to create a pull request")
    if not tests_passed_in_sandbox:
        raise RuntimeError("A pull request requires successful sandboxed test validation")
    if not title.strip() or len(title) > 250:
        raise ValueError("PR title must be between 1 and 250 characters")
    if not expected_head_sha:
        raise ValueError("expected base commit SHA is required")

    head_result = workspace.run(["git", "rev-parse", "HEAD"])
    if not head_result.ok:
        raise RuntimeError("workspace must be a Git repository")
    head_sha = head_result.output.strip()
    if head_sha != expected_head_sha:
        raise RuntimeError("repository HEAD changed during the Forge run; refusing to publish")

    remote_result = workspace.run(["git", "remote", "get-url", "origin"])
    if not remote_result.ok:
        raise RuntimeError("repository must have a GitHub origin remote")
    match = REMOTE_RE.fullmatch(remote_result.output.strip())
    if not match:
        raise ValueError("origin must be a github.com HTTPS or SSH URL")
    owner, repository = match.group(1), match.group(2)
    if repository.endswith(".git"):
        repository = repository[:-4]
    api_repo = f"{API_URL}/repos/{owner}/{repository}"

    status = workspace.run(["git", "status", "--porcelain", "--untracked-files=all"])
    if not status.ok:
        raise RuntimeError("could not inspect Git working tree")
    changed_paths: set[str] = set()
    for line in status.output.splitlines():
        if len(line) < 4:
            continue
        state, relative = line[:2], line[3:].strip()
        if "D" in state or "R" in state or "U" in state:
            raise RuntimeError("PR publication does not support deletions, renames, or unresolved conflicts")
        if relative.startswith('"') and relative.endswith('"'):
            relative = relative[1:-1]
        if relative:
            changed_paths.add(relative.replace("\\", "/"))

    if not changed_paths:
        raise RuntimeError("there are no changes to publish")
    if len(changed_paths) > 50:
        raise RuntimeError("refusing to publish more than 50 changed files")
    for relative in changed_paths:
        if _blocked(relative):
            raise RuntimeError(f"PR publication blocked for protected path: {relative}")
        path = workspace.path(relative)
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"unsupported changed path: {relative}")
        if path.stat().st_size > 200_000:
            raise RuntimeError(f"refusing to publish oversized file: {relative}")

    repository_meta = _request("GET", api_repo, token)
    base = base_branch or repository_meta.get("default_branch") or "main"
    # Ensure the exact local parent commit exists on GitHub before building on it.
    parent = _request("GET", f"{api_repo}/git/commits/{head_sha}", token)
    base_tree = parent.get("tree", {}).get("sha")
    if not base_tree:
        raise RuntimeError("GitHub did not return the parent tree")

    tree_entries: list[dict[str, str]] = []
    for relative in sorted(changed_paths):
        path = workspace.path(relative)
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            raise RuntimeError(f"changed file must be UTF-8 text: {relative}") from exc
        blob = _request("POST", f"{api_repo}/git/blobs", token, json={
            "content": text,
            "encoding": "utf-8",
        })
        tree_entries.append({
            "path": relative,
            "mode": "100644",
            "type": "blob",
            "sha": blob["sha"],
        })

    tree = _request("POST", f"{api_repo}/git/trees", token, json={
        "base_tree": base_tree,
        "tree": tree_entries,
    })
    commit = _request("POST", f"{api_repo}/git/commits", token, json={
        "message": title.strip(),
        "tree": tree["sha"],
        "parents": [head_sha],
    })
    suffix = re.sub(r"[^a-zA-Z0-9-]", "", task_id)[:24] or str(int(time.time()))
    branch = f"forge/{suffix}-{int(time.time())}"
    _request("POST", f"{api_repo}/git/refs", token, json={
        "ref": f"refs/heads/{branch}",
        "sha": commit["sha"],
    })
    pr = _request("POST", f"{api_repo}/pulls", token, json={
        "title": title.strip(),
        "head": branch,
        "base": base,
        "body": body.strip() + (
            "\n\n---\nGenerated by Forge. Changes were validated in the configured "
            "Docker sandbox. This pull request was not merged automatically."
        ),
    })
    return {
        "number": pr.get("number"),
        "url": pr.get("html_url"),
        "branch": branch,
        "base": base,
        "commit_sha": commit["sha"],
        "changed_files": sorted(changed_paths),
    }
