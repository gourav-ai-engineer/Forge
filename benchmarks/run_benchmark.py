from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from forge.engine import ForgeEngine
from forge.tools import ToolRegistry
from forge.types import ForgeTask, ToolCall
from forge.workspace import Workspace


def case_offline_inspection() -> tuple[bool, float, str]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
        (root / "test_sample.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8")
        started = time.perf_counter()
        report = ForgeEngine().run(ForgeTask(request="inspect and validate", repo_path=str(root)))
        elapsed = (time.perf_counter() - started) * 1000
        return report.status == "succeeded", elapsed, report.summary


def case_write_gate() -> tuple[bool, float, str]:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Workspace(tmp)
        registry = ToolRegistry(workspace, allow_writes=False)
        started = time.perf_counter()
        result = registry.execute(ToolCall("write_file", {"path": "blocked.txt", "content": "x"}))
        elapsed = (time.perf_counter() - started) * 1000
        passed = (not result.ok) and not (Path(tmp) / "blocked.txt").exists()
        return passed, elapsed, result.error


def case_commit_gate() -> tuple[bool, float, str]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        workspace = Workspace(tmp)
        registry = ToolRegistry(workspace, allow_writes=False)
        started = time.perf_counter()
        result = registry.execute(ToolCall("git_commit", {"message": "benchmark"}))
        elapsed = (time.perf_counter() - started) * 1000
        return (not result.ok and "approval" in result.error.lower()), elapsed, result.error


def case_path_boundary() -> tuple[bool, float, str]:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Workspace(tmp)
        started = time.perf_counter()
        try:
            workspace.path("../escape.txt")
            passed = False
            detail = "path traversal was not rejected"
        except ValueError as exc:
            passed = True
            detail = str(exc)
        elapsed = (time.perf_counter() - started) * 1000
        return passed, elapsed, detail


def case_credential_filtering() -> tuple[bool, float, str]:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Workspace(tmp)
        original = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "benchmark-secret"
        started = time.perf_counter()
        try:
            result = workspace.run(["python", "-c", "import os; print(os.getenv('OPENAI_API_KEY', 'MISSING'))"])
        finally:
            if original is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = original
        elapsed = (time.perf_counter() - started) * 1000
        passed = result.ok and "benchmark-secret" not in result.output
        return passed, elapsed, result.output.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Forge's reproducible runtime benchmark")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    cases = [
        ("offline_inspection", case_offline_inspection),
        ("write_authorization_gate", case_write_gate),
        ("commit_authorization_gate", case_commit_gate),
        ("workspace_path_boundary", case_path_boundary),
        ("credential_filtering", case_credential_filtering),
    ]
    results = []
    for name, fn in cases:
        try:
            passed, elapsed_ms, detail = fn()
        except Exception as exc:  # benchmark must report failures instead of hiding them
            passed, elapsed_ms, detail = False, 0.0, f"{type(exc).__name__}: {exc}"
        results.append({"case": name, "passed": passed, "duration_ms": round(elapsed_ms, 2), "detail": detail})

    pass_count = sum(item["passed"] for item in results)
    durations = [item["duration_ms"] for item in results]
    payload = {
        "benchmark": "forge-runtime-safety-v1",
        "cases": len(results),
        "passed": pass_count,
        "success_rate_percent": round(pass_count / len(results) * 100, 2),
        "median_runtime_ms": round(statistics.median(durations), 2),
        "results": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Forge benchmark: {pass_count}/{len(results)} cases passed ({payload['success_rate_percent']}%).")
        print(f"Median runtime: {payload['median_runtime_ms']} ms")
        for item in results:
            status = "PASS" if item["passed"] else "FAIL"
            print(f"[{status}] {item['case']}: {item['duration_ms']} ms")

    raise SystemExit(0 if pass_count == len(results) else 1)


if __name__ == "__main__":
    main()
