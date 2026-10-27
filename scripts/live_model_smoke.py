from __future__ import annotations

import os
import tempfile
from pathlib import Path

from forge.engine import ForgeEngine
from forge.providers import OpenAIPlanner
from forge.types import ForgeTask, RunStatus


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="forge-live-") as raw_root:
        root = Path(raw_root)
        (root / "calculator.py").write_text(
            "def add(a, b):\n    return a - b\n",
            encoding="utf-8",
        )
        (root / "test_calculator.py").write_text(
            "from calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
            encoding="utf-8",
        )
        task = ForgeTask(
            request="Fix calculator.py so the test passes. Inspect first, make the minimal edit, then run the tests.",
            repo_path=str(root),
            max_steps=14,
            require_approval_for_write=False,
        )
        previous_unsandboxed = os.environ.get("FORGE_ALLOW_UNSANDBOXED_TESTS")
        os.environ["FORGE_ALLOW_UNSANDBOXED_TESTS"] = "1"
        try:
            report = ForgeEngine(planner=OpenAIPlanner(), max_rounds=3).run(
                task,
                allow_writes=True,
            )
        finally:
            if previous_unsandboxed is None:
                os.environ.pop("FORGE_ALLOW_UNSANDBOXED_TESTS", None)
            else:
                os.environ["FORGE_ALLOW_UNSANDBOXED_TESTS"] = previous_unsandboxed
        print(f"status={report.status.value}")
        for step in report.steps:
            print(f"{step.index:02d} {step.tool} {'OK' if step.ok else 'ERROR'}")
        return 0 if report.status is RunStatus.SUCCEEDED else 1


if __name__ == "__main__":
    raise SystemExit(main())
