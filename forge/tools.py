from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .analyzer import analyze_repository
from .retrieval import CodeRetriever
from .sandbox import SandboxRunner
from .types import ToolCall, ToolResult
from .workspace import Workspace

READ_ONLY_TOOLS = {
    "repo_tree", "repo_analyze", "read_file", "search_text", "search_code",
    "git_status", "git_diff", "run_tests",
}
WRITE_TOOLS = {"write_file", "git_commit"}


class ToolRegistry:
    def __init__(
        self,
        workspace: Workspace,
        *,
        allow_writes: bool = False,
        sandbox: bool = False,
    ) -> None:
        self.workspace = workspace
        self.allow_writes = allow_writes
        self.sandbox = sandbox
        self.sandbox_runner = SandboxRunner(workspace.root) if sandbox else None
        self.code_retriever = CodeRetriever(workspace.root)

    def execute(self, call: ToolCall) -> ToolResult:
        try:
            if call.name == "repo_tree":
                return ToolResult(True, "\n".join(self.workspace.list_files()))
            if call.name == "repo_analyze":
                profile = analyze_repository(self.workspace.root)
                return ToolResult(True, str({
                    "languages": profile.languages,
                    "file_count": profile.file_count,
                    "has_git": profile.has_git,
                    "test_command": profile.test_command,
                    "build_command": profile.build_command,
                }))
            if call.name == "read_file":
                return ToolResult(True, self.workspace.read(str(call.arguments["path"])))
            if call.name == "search_text":
                return self._search(str(call.arguments["query"]))
            if call.name == "search_code":
                query = str(call.arguments["query"])
                limit = int(call.arguments.get("limit", 8))
                results = self.code_retriever.search(query, limit=limit)
                return ToolResult(True, json.dumps({
                    "retrieval_mode": self.code_retriever.mode,
                    "count": len(results),
                    "results": results,
                }, ensure_ascii=False))
            if call.name == "write_file":
                return ToolResult(True, self.workspace.write(
                    str(call.arguments["path"]),
                    str(call.arguments["content"]),
                    self.allow_writes,
                ))
            if call.name == "git_status":
                return self._git_status()
            if call.name == "git_diff":
                return self._git_diff()
            if call.name == "git_commit":
                return self._git_commit(
                    str(call.arguments.get("message", "forge: apply changes")),
                    call.arguments.get("paths", []),
                )
            if call.name == "run_tests":
                return self._run_tests()
            return ToolResult(False, "", f"unknown tool: {call.name}")
        except (KeyError, TypeError, ValueError, FileNotFoundError, PermissionError) as exc:
            return ToolResult(False, "", f"tool error: {exc}")

    def _search(self, query: str) -> ToolResult:
        if not query or len(query) > 500:
            return ToolResult(False, "", "query must be 1-500 characters")
        matches: list[str] = []
        for relative in self.workspace.list_files():
            try:
                text = self.workspace.read(relative, max_bytes=250_000)
            except (OSError, ValueError, PermissionError):
                continue
            if query.casefold() in text.casefold():
                matches.append(relative)
        return ToolResult(True, "\n".join(matches[:100]))

    def _git_status(self) -> ToolResult:
        if not (self.workspace.root / ".git").exists():
            return ToolResult(True, "Not a Git repository; Git status unavailable.")
        return self.workspace.run(["git", "status", "--short"])

    def _git_diff(self) -> ToolResult:
        if not (self.workspace.root / ".git").exists():
            return ToolResult(True, "Not a Git repository; Git diff unavailable.")
        return self.workspace.run(["git", "diff", "--", "."])

    def _git_commit(self, message: str, paths: object) -> ToolResult:
        if not self.allow_writes:
            return ToolResult(False, "", "Git commit requires approval")
        if not (self.workspace.root / ".git").exists():
            return ToolResult(False, "", "not a Git repository")
        if not message.strip() or len(message) > 120:
            return ToolResult(False, "", "commit message must be 1-120 characters")
        if not isinstance(paths, list) or not paths or len(paths) > 30:
            return ToolResult(False, "", "git_commit requires an explicit paths list (1-30 files)")

        validated: list[str] = []
        for item in paths:
            if not isinstance(item, str):
                return ToolResult(False, "", "each commit path must be a string")
            relative = item.replace("\\", "/")
            target = self.workspace.path(relative, for_write=True)
            if not target.is_file():
                return ToolResult(False, "", f"commit path is not a file: {relative}")
            validated.append(relative)

        staged_before = self.workspace.run(["git", "diff", "--cached", "--name-only"])
        if not staged_before.ok:
            return staged_before
        staged_paths = {line.strip().replace("\\", "/") for line in staged_before.output.splitlines() if line.strip()}
        if staged_paths.difference(validated):
            return ToolResult(False, "", "unrelated staged changes exist; refusing to commit them")

        staged = self.workspace.run(["git", "add", "--", *validated])
        if not staged.ok:
            return staged
        return self.workspace.run(["git", "commit", "-m", message])

    def _clear_python_bytecode(self) -> None:
        """Prevent stale timestamp-based .pyc files from masking freshly written source."""
        ignored = {".git", ".forge", ".venv", "venv", "node_modules", "site-packages"}
        for current, directories, _ in os.walk(self.workspace.root, topdown=True, followlinks=False):
            directories[:] = [
                name for name in directories
                if name.casefold() not in ignored and not (Path(current) / name).is_symlink()
            ]
            if "__pycache__" in directories:
                cache_dir = Path(current) / "__pycache__"
                directories.remove("__pycache__")
                if not cache_dir.is_symlink():
                    shutil.rmtree(cache_dir, ignore_errors=True)

    def _run_tests(self) -> ToolResult:
        if (self.workspace.root / "pyproject.toml").exists() or (self.workspace.root / "pytest.ini").exists():
            command = ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
        elif (self.workspace.root / "package.json").exists():
            command = ["npm", "test", "--", "--runInBand"]
        elif (self.workspace.root / "go.mod").exists():
            command = ["go", "test", "./..."]
        else:
            return ToolResult(True, "SKIPPED: no supported test runner detected; inspection only.")

        # A prior baseline run may have created timestamp-based bytecode. Clear it
        # before validation so same-size edits made within one second are actually tested.
        self._clear_python_bytecode() if command[0] == "python" else None
        if self.sandbox_runner is not None:
            return self.sandbox_runner.run(command, timeout_seconds=180)
        if os.getenv("FORGE_ALLOW_UNSANDBOXED_TESTS") != "1":
            return ToolResult(
                True,
                "SKIPPED: test execution requires --sandbox. Host execution is disabled by default.",
                metadata={"skipped": True},
            )
        return self.workspace.run(command, timeout_seconds=180)
