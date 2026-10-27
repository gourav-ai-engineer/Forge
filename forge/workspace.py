from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .types import ToolResult


class Workspace:
    """File/command boundary scoped to one repository root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        if not self.root.exists() or not self.root.is_dir():
            raise ValueError(f"Workspace does not exist: {self.root}")

    def path(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("Path escapes workspace")
        return candidate

    def read(self, relative: str, max_bytes: int = 100_000) -> str:
        target = self.path(relative)
        if not target.is_file():
            raise FileNotFoundError(relative)
        data = target.read_bytes()
        if len(data) > max_bytes:
            raise ValueError(f"File exceeds {max_bytes} bytes")
        return data.decode("utf-8", errors="replace")

    def write(self, relative: str, content: str, allow_write: bool) -> str:
        if not allow_write:
            raise PermissionError("Write requires approval")
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote {relative} ({len(content)} chars)"

    def list_files(self, limit: int = 250) -> list[str]:
        ignored = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
        files: list[str] = []
        for path in self.root.rglob("*"):
            if any(part in ignored for part in path.parts):
                continue
            if path.is_file():
                files.append(path.relative_to(self.root).as_posix())
                if len(files) >= limit:
                    break
        return sorted(files)

    def run(self, command: list[str], timeout_seconds: int = 120) -> ToolResult:
        """Run a command with no shell and a clean child environment."""
        if not command or any("\x00" in part for part in command):
            return ToolResult(False, "", "invalid command")
        env = os.environ.copy()
        env.pop("OPENAI_API_KEY", None)
        env.pop("GITHUB_TOKEN", None)
        try:
            proc = subprocess.run(
                command,
                cwd=self.root,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(False, "", "command timed out")
        output = (proc.stdout + proc.stderr).strip()
        return ToolResult(
            proc.returncode == 0,
            output[-20_000:],
            metadata={"returncode": proc.returncode},
        )
