from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class RunStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ForgeTask:
    request: str
    repo_path: str
    task_id: str = ""
    max_steps: int = 12
    timeout_seconds: int = 120
    require_approval_for_write: bool = True


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: str
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StepRecord:
    index: int
    tool: str
    ok: bool
    output: str
    duration_ms: float


@dataclass(frozen=True)
class RunReport:
    task_id: str
    status: RunStatus
    summary: str
    steps: tuple[StepRecord, ...]
    started_at: str
    finished_at: str

    @staticmethod
    def timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()
