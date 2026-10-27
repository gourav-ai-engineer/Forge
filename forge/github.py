from __future__ import annotations

import os
import re
from dataclasses import dataclass

import requests


ISSUE_URL = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/issues/(\d+)/?$")


@dataclass(frozen=True)
class GitHubIssue:
    owner: str
    repository: str
    number: int
    title: str
    body: str
    url: str

    @property
    def task_request(self) -> str:
        body = self.body.strip() or "No issue body provided."
        return f"GitHub issue #{self.number}: {self.title.strip()}\n\n{body}"


def parse_issue_url(url: str) -> tuple[str, str, int]:
    match = ISSUE_URL.fullmatch(url.strip())
    if not match:
        raise ValueError("expected a public GitHub issue URL")
    return match.group(1), match.group(2), int(match.group(3))


def fetch_issue(url: str, *, timeout_seconds: int = 10) -> GitHubIssue:
    owner, repository, number = parse_issue_url(url)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Forge-Autonomous-Engineer"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(
        f"https://api.github.com/repos/{owner}/{repository}/issues/{number}",
        headers=headers,
        timeout=timeout_seconds,
    )
    if response.status_code != 200:
        raise RuntimeError(f"GitHub issue fetch failed with HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict) or "title" not in payload:
        raise RuntimeError("GitHub returned an invalid issue payload")
    return GitHubIssue(
        owner=owner,
        repository=repository,
        number=number,
        title=str(payload["title"]),
        body=str(payload.get("body") or ""),
        url=url,
    )
