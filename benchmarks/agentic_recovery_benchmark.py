from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from forge.engine import ForgeEngine
from forge.planner import Planner
from forge.types import ForgeTask, ToolCall


class DeterministicRepairPlanner:
    """Deterministic stand-in for an LLM planner used to benchmark the agent loop."""

    def __init__(self) -> None:
        self.rounds = 0

    def plan(self, task: ForgeTask, context: str) -> tuple[ToolCall, ...]:
        self.rounds += 1
        if self.rounds == 1:
            return (
                ToolCall("read_file", {"path": "calculator.py"}, "Inspect the failing implementation."),
                ToolCall("write_file", {
                    "path": "calculator.py",
                    "content": "def add(a, b):\n    return a + b\n",
                }, "Repair the identified arithmetic defect."),
                ToolCall("git_diff", reason="Review the repair before validation."),
                ToolCall("run_tests", reason="Validate the repair."),
            )
        return ()


def run_case() -> tuple[bool, float, dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "calculator.py").write_text(
            "def add(a, b):\n    return a - b\n", encoding="utf-8"
        )
        (root / "test_calculator.py").write_text(
            "from calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
            encoding="utf-8",
        )
        # Pin test discovery so the intentionally broken fixture always fails the
        # Forge baseline before the planner repairs it.
        (root / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\ntestpaths = [\"test_calculator.py\"]\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "-c", "user.name=Forge Benchmark", "-c",
             "user.email=forge-benchmark@example.invalid", "commit", "-qm", "fixture"],
            check=True,
        )

        fixture_baseline = subprocess.run(
            ["python", "-m", "pytest", "-q"], cwd=root, capture_output=True, text=True, check=False
        )
        planner: Planner = DeterministicRepairPlanner()
        started = time.perf_counter()
        report = ForgeEngine(planner=planner, max_rounds=2).run(
            ForgeTask(
                request="Fix the failing calculator tests.",
                repo_path=str(root),
                max_steps=12,
                require_approval_for_write=False,
            ),
            allow_writes=True,
        )
        elapsed = (time.perf_counter() - started) * 1000

        final_code = (root / "calculator.py").read_text(encoding="utf-8")
        final_tests = subprocess.run(
            ["python", "-m", "pytest", "-q"], cwd=root, capture_output=True, text=True, check=False
        )
        test_steps = [step for step in report.steps if step.tool == "run_tests"]
        passed = (
            fixture_baseline.returncode != 0
            and report.status == "succeeded"
            and "return a + b" in final_code
            and final_tests.returncode == 0
            and any(not step.ok for step in test_steps[:-1])
            and test_steps[-1].ok
            and any(step.tool == "write_file" and step.ok for step in report.steps)
            and any(step.tool == "git_diff" and step.ok for step in report.steps)
        )
        detail = {
            "status": report.status,
            "steps": len(report.steps),
            "fixture_baseline_failed": fixture_baseline.returncode != 0,
            "forge_baseline_failed": bool(test_steps and not test_steps[0].ok),
            "final_test_passed": bool(test_steps and test_steps[-1].ok),
            "write_executed": any(step.tool == "write_file" and step.ok for step in report.steps),
            "diff_reviewed": any(step.tool == "git_diff" and step.ok for step in report.steps),
            "external_final_tests_exit_code": final_tests.returncode,
            "summary": report.summary,
        }
        return passed, elapsed, detail


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Forge's inspect-repair-validate loop")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    started = time.perf_counter()
    passed, elapsed_ms, detail = run_case()
    payload = {
        "benchmark": "forge-agentic-recovery-v1",
        "cases": 1,
        "passed": int(passed),
        "success_rate_percent": 100.0 if passed else 0.0,
        "runtime_ms": round(elapsed_ms, 2),
        "wall_clock_ms": round((time.perf_counter() - started) * 1000, 2),
        "results": [{"case": "autonomous_bug_repair", "passed": passed, "duration_ms": round(elapsed_ms, 2), "detail": detail}],
        "methodology": "Deterministic planner fixture validates the same engine/tool/recovery path without fabricating LLM quality metrics.",
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] autonomous_bug_repair: {elapsed_ms:.2f} ms")
        print(json.dumps(detail, indent=2))

    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
