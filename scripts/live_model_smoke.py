from __future__ import annotations

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
        report = ForgeEngine(planner=OpenAIPlanner(), max_rounds=3).run(
            task,
            allow_writes=True,
        )
        print(f"status={report.status.value}")
        for step in report.steps:
            print(f"{step.index:02d} {step.tool} {'OK' if step.ok else 'ERROR'}")
        return 0 if report.status is RunStatus.SUCCEEDED else 1


if __name__ == "__main__":
    raise SystemExit(main())
