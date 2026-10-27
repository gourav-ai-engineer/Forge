from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from forge.engine import ForgeEngine
from forge.github import fetch_issue
from forge.providers import provider_from_env
from forge.types import ForgeTask
from forge.workspace import Workspace


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Forge — autonomous software engineer")
    parser.add_argument("request", nargs="?", default="Inspect this repository and run its tests.")
    parser.add_argument("--repo", default=".", help="local repository/workspace path")
    parser.add_argument("--issue", help="public GitHub issue URL to use as the task")
    parser.add_argument("--allow-writes", action="store_true", help="allow approved file edits and commits")
    parser.add_argument("--sandbox", action="store_true", help="validate in a hardened Docker sandbox")
    parser.add_argument("--create-pr", action="store_true", help="open an unmerged PR after sandbox tests pass")
    parser.add_argument("--pr-title", help="optional pull-request title")
    parser.add_argument("--pr-base", help="optional pull-request base branch; defaults to repository default")
    parser.add_argument("--max-steps", type=int, default=16)
    parser.add_argument("--serve", action="store_true", help="start the local read-only FastAPI service")
    parser.add_argument("--host", default="127.0.0.1", help="API host (non-local binding requires FORGE_API_KEY)")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.max_steps < 1 or args.max_steps > 100:
        parser.error("--max-steps must be between 1 and 100")
    if args.port < 1 or args.port > 65535:
        parser.error("--port must be 1-65535")
    if args.sandbox and not args.allow_writes:
        parser.error("--sandbox is intended for mutation-enabled runs; add --allow-writes")
    if args.create_pr and not (args.allow_writes and args.sandbox):
        parser.error("--create-pr requires both --allow-writes and --sandbox")

    repo_root = Path(args.repo).resolve()
    if args.serve:
        from forge.server import serve
        os.environ["FORGE_WORKSPACE"] = str(repo_root)
        serve(host=args.host, port=args.port)
        return

    initial_head_sha: str | None = None
    if args.create_pr:
        workspace = Workspace(repo_root)
        status = workspace.run(["git", "status", "--porcelain", "--untracked-files=all"])
        if not status.ok:
            parser.error("--create-pr requires a valid Git repository")
        if status.output.strip():
            parser.error("--create-pr requires a clean working tree before the run")
        head = workspace.run(["git", "rev-parse", "HEAD"])
        if not head.ok or not head.output.strip():
            parser.error("could not determine repository HEAD")
        initial_head_sha = head.output.strip()

    request = args.request
    issue = None
    if args.issue:
        try:
            issue = fetch_issue(args.issue)
        except (ValueError, RuntimeError) as exc:
            parser.error(str(exc))
        request = issue.task_request

    planner = provider_from_env()
    report = ForgeEngine(planner=planner, sandbox=args.sandbox).run(
        ForgeTask(
            request=request,
            repo_path=str(repo_root),
            max_steps=args.max_steps,
            require_approval_for_write=not args.allow_writes,
        ),
        allow_writes=args.allow_writes,
    )
    payload = {
        "task_id": report.task_id,
        "status": report.status.value,
        "summary": report.summary,
        "issue": issue.url if issue else None,
        "repository": f"{issue.owner}/{issue.repository}" if issue else None,
        "steps": [
            {
                "index": step.index,
                "tool": step.tool,
                "ok": step.ok,
                "output": step.output,
                "duration_ms": round(step.duration_ms, 2),
            }
            for step in report.steps
        ],
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "model_planner": bool(planner),
        "sandbox": args.sandbox,
    }

    pr_failed = False
    if args.create_pr:
        validations = [step for step in report.steps if step.tool == "run_tests"]
        tests_passed = bool(
            report.status.value == "succeeded"
            and validations
            and validations[-1].ok
            and not validations[-1].output.startswith("SKIPPED:")
            and args.sandbox
        )
        if not tests_passed or initial_head_sha is None:
            payload["pull_request"] = {
                "status": "not_created",
                "reason": "Forge did not complete a successful sandboxed validation run.",
            }
            pr_failed = True
        else:
            try:
                from forge.github_pr import create_pull_request
                workspace = Workspace(repo_root)
                title = args.pr_title or f"Forge: {request.strip().splitlines()[0][:180]}"
                payload["pull_request"] = create_pull_request(
                    workspace,
                    title=title,
                    body=(
                        "## Summary\n\n"
                        f"Task: {request.strip()}\n\n"
                        "## Validation\n\n"
                        "- The Forge run completed successfully.\n"
                        "- Test validation ran in the configured Docker sandbox.\n"
                        "- This PR requires human review; Forge does not auto-merge."
                    ),
                    expected_head_sha=initial_head_sha,
                    task_id=report.task_id,
                    tests_passed_in_sandbox=True,
                    base_branch=args.pr_base,
                )
            except (RuntimeError, ValueError, OSError) as exc:
                payload["pull_request"] = {"status": "not_created", "reason": str(exc)}
                pr_failed = True

    print(json.dumps(payload, indent=2) if args.json else payload["summary"])
    if args.create_pr and pr_failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
