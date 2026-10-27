from __future__ import annotations

from .analyzer import analyze_repository
from .sandbox import SandboxRunner
from .types import ToolCall, ToolResult
from .workspace import Workspace


READ_ONLY_TOOLS = {
    "repo_tree",
    "repo_analyze",
    "read_file",
    "search_text",
    "git_status",
    "git_diff",
    "run_tests",
}
WRITE_TOOLS = {"write_file", "git_commit"}


class ToolRegistry:
    def __init__(self, workspace: Workspace, *, allow_writes: bool = False, sandbox: bool = False) -> None:
        self.workspace = workspace
        self.allow_writes = allow_writes
        self.sandbox = sandbox
        self.sandbox_runner = SandboxRunner(workspace.root) if sandbox else None

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
            if call.name == "write_file":
                return ToolResult(True, self.workspace.write(
                    str(call.arguments["path"]), str(call.arguments["content"]), self.allow_writes
                ))
            if call.name == "git_status":
                return self._git_status()
            if call.name == "git_diff":
                return self._git_diff()
            if call.name == "git_commit":
                return self._git_commit(str(call.arguments.get("message", "forge: apply changes")))
            if call.name == "run_tests":
                return self._run_tests()
            return ToolResult(False, "", f"unknown tool: {call.name}")
        except (KeyError, TypeError, ValueError, FileNotFoundError, PermissionError) as exc:
            return ToolResult(False, "", f"tool error: {exc}")

    def _search(self, query: str) -> ToolResult:
        if not query or len(query) > 500:
            return ToolResult(False, "", "query must be 1-500 characters")
        matches: list[str] = []
        for rel in self.workspace.list_files():
            path = self.workspace.path(rel)
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if query.casefold() in text.casefold():
                matches.append(rel)
        return ToolResult(True, "\n".join(matches[:100]))

    def _git_status(self) -> ToolResult:
        if not (self.workspace.root / ".git").exists():
            return ToolResult(True, "Not a Git repository; Git status unavailable.")
        return self.workspace.run(["git", "status", "--short"])

    def _git_diff(self) -> ToolResult:
        if not (self.workspace.root / ".git").exists():
            return ToolResult(True, "Not a Git repository; Git diff unavailable.")
        return self.workspace.run(["git", "diff", "--", "."])

    def _git_commit(self, message: str) -> ToolResult:
        if not self.allow_writes:
            return ToolResult(False, "", "Git commit requires approval")
        if not (self.workspace.root / ".git").exists():
            return ToolResult(False, "", "not a Git repository")
        if not message.strip() or len(message) > 120:
            return ToolResult(False, "", "commit message must be 1-120 characters")
        staged = self.workspace.run(["git", "add", "--", "."])
        if not staged.ok:
            return staged
        return self.workspace.run(["git", "commit", "-m", message])

    def _run_tests(self) -> ToolResult:
        if (self.workspace.root / "pyproject.toml").exists() or (self.workspace.root / "pytest.ini").exists():
            command = ["python", "-m", "pytest", "-q"]
        elif (self.workspace.root / "package.json").exists():
            command = ["npm", "test", "--", "--runInBand"]
        elif (self.workspace.root / "go.mod").exists():
            command = ["go", "test", "./..."]
        else:
            return ToolResult(True, "No supported test runner detected; inspection required.")

        if self.sandbox_runner is not None:
            return self.sandbox_runner.run(command, timeout_seconds=180)
        return self.workspace.run(command, timeout_seconds=180)
