from __future__ import annotations

import os
import subprocess
from pathlib import Path, PureWindowsPath

from .types import ToolResult

IGNORED_DIRS = {
    ".git", ".forge", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", ".tox", ".idea", ".vscode",
}
PROTECTED_DIRS = {".git", ".forge", ".ssh", ".aws", ".kube"}
PROTECTED_NAMES = {"id_rsa", "id_ed25519", "credentials.json", ".env"}
PROTECTED_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}


class Workspace:
    """Path-safe file and command boundary scoped to a single repository."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        if not self.root.exists() or not self.root.is_dir():
            raise ValueError(f"Workspace does not exist: {self.root}")

    @staticmethod
    def _sensitive_parts(relative: str) -> bool:
        parts = [part.casefold() for part in Path(relative).parts]
        if any(part in PROTECTED_DIRS for part in parts):
            return True
        name = Path(relative).name.casefold()
        if name in PROTECTED_NAMES:
            return True
        if name.startswith(".env.") and name != ".env.example":
            return True
        if Path(name).suffix in PROTECTED_SUFFIXES:
            return True
        if "credentials" in name or "secrets" in name:
            return True
        return False

    def path(self, relative: str, *, for_write: bool = False) -> Path:
        if not isinstance(relative, str) or not relative.strip():
            raise ValueError("path must be a non-empty relative string")
        if Path(relative).is_absolute() or PureWindowsPath(relative).is_absolute():
            raise ValueError("absolute paths are not allowed")
        normalized = relative.replace("\\", "/")
        if any(part == ".." for part in normalized.split("/")):
            raise ValueError("parent path components are not allowed")
        candidate = self.root / Path(normalized)
        current = self.root
        for part in Path(normalized).parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("symbolic links are not allowed")
        resolved = candidate.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise ValueError("Path escapes workspace")
        relative_resolved = resolved.relative_to(self.root).as_posix()
        if self._sensitive_parts(relative_resolved):
            raise ValueError("access to protected paths is denied")
        parts = [part.casefold() for part in Path(relative_resolved).parts]
        if for_write and parts and parts[0] == ".github":
            raise ValueError("writes to GitHub automation/configuration paths are blocked")
        return resolved

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
        if len(content.encode("utf-8")) > 200_000:
            raise ValueError("file content exceeds 200000 bytes")
        target = self.path(relative, for_write=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote {relative} ({len(content)} chars)"

    def list_files(self, limit: int = 250) -> list[str]:
        files: list[str] = []
        for path in self.root.rglob("*"):
            try:
                relative = path.relative_to(self.root).as_posix()
                if path.is_symlink():
                    continue
                if any(part.casefold() in IGNORED_DIRS for part in path.relative_to(self.root).parts):
                    continue
                if not path.is_file() or self._sensitive_parts(relative):
                    continue
                files.append(relative)
                if len(files) >= limit:
                    break
            except (OSError, ValueError):
                continue
        return sorted(files)

    def run(self, command: list[str], timeout_seconds: int = 120) -> ToolResult:
        """Run argv without a shell and with an allowlisted child environment."""
        if not command or any("\x00" in part for part in command):
            return ToolResult(False, "", "invalid command")
        allowed_environment = {
            "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR", "COMSPEC",
            "PATHEXT", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "VIRTUAL_ENV",
            "PYTHONPATH", "PYTHONIOENCODING", "APPDATA", "LOCALAPPDATA",
        }
        env = {key: value for key, value in os.environ.items() if key.upper() in allowed_environment}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
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
        except OSError as exc:
            return ToolResult(False, "", f"command could not start: {exc}")
        output = (proc.stdout + proc.stderr).strip()
        return ToolResult(
            proc.returncode == 0,
            output[-20_000:],
            metadata={"returncode": proc.returncode},
        )
