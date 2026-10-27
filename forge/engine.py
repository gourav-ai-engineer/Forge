from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from .planner import OfflinePlanner, Planner
from .state import RunStore
from .tools import ToolRegistry
from .types import ForgeTask, RunReport, RunStatus, StepRecord, ToolCall
from .workspace import Workspace


@dataclass
class ForgeEngine:
    """Agent runtime with inspect -> plan -> act -> validate and bounded recovery."""

    planner: Planner | None = None
    max_rounds: int = 3
    state_dir: str = ".forge/runs"
    sandbox: bool = False

    def _execute(self, registry: ToolRegistry, calls: tuple[ToolCall, ...], records: list[StepRecord], offset: int) -> None:
        for index, call in enumerate(calls, start=offset):
            started = time.perf_counter()
            result = registry.execute(call)
            records.append(StepRecord(index, call.name, result.ok, result.output if result.ok else result.error,
                                      (time.perf_counter() - started) * 1000))

    def _finish(self, report: RunReport, workspace: Workspace) -> RunReport:
        RunStore(workspace.root / self.state_dir).save(report)
        return report

    @staticmethod
    def _validated_success(records: list[StepRecord]) -> bool:
        """Treat an expected failing baseline as recoverable when a later validation passes."""
        if not records:
            return False
        validations = [step for step in records if step.tool == "run_tests"]
        if not validations or not validations[-1].ok:
            return False
        non_recoverable_failures = [
            step for step in records
            if not step.ok and step.tool != "run_tests"
        ]
        return not non_recoverable_failures

    def run(self, task: ForgeTask, *, allow_writes: bool | None = None) -> RunReport:
        if task.max_steps < 1 or task.max_steps > 100:
            raise ValueError("max_steps must be between 1 and 100")
        if self.max_rounds < 1 or self.max_rounds > 10:
            raise ValueError("max_rounds must be between 1 and 10")

        task_id = task.task_id or uuid.uuid4().hex[:12]
        started_at = RunReport.timestamp()
        workspace = Workspace(task.repo_path)
        approved = task.require_approval_for_write is False if allow_writes is None else allow_writes
        registry = ToolRegistry(workspace, allow_writes=approved, sandbox=self.sandbox and approved)
        planner = self.planner or OfflinePlanner()
        records: list[StepRecord] = []

        baseline = (
            ToolCall("repo_analyze", reason="Identify repository language and validation entry points."),
            ToolCall("repo_tree", reason="Inspect the repository before any action."),
            ToolCall("git_status", reason="Establish the working-tree state."),
            ToolCall("run_tests", reason="Establish a validation baseline."),
        )
        self._execute(registry, baseline, records, 1)

        if isinstance(planner, OfflinePlanner):
            ok = all(step.ok for step in records)
            return self._finish(
                RunReport(task_id, RunStatus.SUCCEEDED if ok else RunStatus.FAILED,
                          "Offline inspect/test cycle completed." if ok else "Baseline validation failed.",
                          tuple(records), started_at, RunReport.timestamp()), workspace)

        next_index = len(records) + 1
        rounds = 0
        while rounds < self.max_rounds and len(records) < task.max_steps:
            rounds += 1
            context = "\n\n".join(
                f"{s.tool}: {'OK' if s.ok else 'ERROR'}\n{s.output}" for s in records
            )[-40_000:]
            calls = planner.plan(task, context)[: task.max_steps - len(records)]
            if not calls:
                break
            self._execute(registry, calls, records, next_index)
            next_index = len(records) + 1
            if records and records[-1].tool == "run_tests" and records[-1].ok:
                break

        if len(records) < task.max_steps and any(s.tool == "write_file" and s.ok for s in records):
            self._execute(registry, (ToolCall("git_diff", reason="Review the final change set."),), records, next_index)
            next_index = len(records) + 1
            if len(records) < task.max_steps:
                self._execute(registry, (ToolCall("run_tests", reason="Validate the reviewed change set."),), records, next_index)

        ok = self._validated_success(records)
        summary = "Autonomous execution loop completed." if ok else "Agent execution needs another repair cycle."
        return self._finish(
            RunReport(task_id, RunStatus.SUCCEEDED if ok else RunStatus.FAILED,
                      summary, tuple(records), started_at, RunReport.timestamp()), workspace)
