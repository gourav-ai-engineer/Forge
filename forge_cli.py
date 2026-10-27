from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from forge.engine import ForgeEngine
from forge.github import fetch_issue
from forge.providers import provider_from_env
from forge.types import ForgeTask


def main() -> None:
    parser = argparse.ArgumentParser(description="Forge — autonomous software engineer")
    parser.add_argument("request", nargs="?", default="Inspect this repository and run its tests.")
    parser.add_argument("--repo", default=".", help="repository/workspace path")
    parser.add_argument("--issue", help="public GitHub issue URL to use as the task")
    parser.add_argument("--allow-writes", action="store_true", help="allow write_file and git_commit tools")
    parser.add_argument("--sandbox", action="store_true", help="run validation in a hardened Docker sandbox")
    parser.add_argument("--max-steps", type=int, default=16)
    parser.add_argument("--serve", action="store_true", help="start the local read-only HTTP API")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.max_steps < 1 or args.max_steps > 100:
        parser.error("--max-steps must be between 1 and 100")
    if args.port < 1 or args.port > 65535:
        parser.error("--port must be 1-65535")
    if args.sandbox and not args.allow_writes:
        parser.error("--sandbox is intended for mutation-enabled agent runs; add --allow-writes")

    if args.serve:
        from forge.server import serve
        os.environ["FORGE_WORKSPACE"] = str(Path(args.repo).resolve())
        serve(port=args.port)
        return

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
            repo_path=str(Path(args.repo).resolve()),
            max_steps=args.max_steps,
            require_approval_for_write=not args.allow_writes,
        ),
        allow_writes=args.allow_writes,
    )
    payload = {
        "task_id": report.task_id,
        "status": report.status,
        "summary": report.summary,
        "issue": issue.url if issue else None,
        "repository": f"{issue.owner}/{issue.repository}" if issue else None,
        "steps": [
            {"index": s.index, "tool": s.tool, "ok": s.ok, "output": s.output, "duration_ms": round(s.duration_ms, 2)}
            for s in report.steps
        ],
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "model_planner": bool(planner),
        "sandbox": args.sandbox,
    }
    print(json.dumps(payload, indent=2) if args.json else payload["summary"])


if __name__ == "__main__":
    main()
