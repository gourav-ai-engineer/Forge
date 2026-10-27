from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .types import ToolResult


class SandboxRunner:
    """Run validation in a disposable, network-isolated Docker copy."""

    def __init__(
        self,
        workspace: Path,
        *,
        image: str | None = None,
        memory: str = "1g",
        cpus: str = "2",
        pids_limit: int = 128,
    ) -> None:
        self.workspace = workspace.resolve()
        self.image = image or os.getenv("FORGE_SANDBOX_IMAGE", "forge-sandbox:local")
        self.memory = memory
        self.cpus = cpus
        self.pids_limit = pids_limit

    def run(self, command: list[str], timeout_seconds: int = 180) -> ToolResult:
        if not command or any("\x00" in part for part in command):
            return ToolResult(False, "", "invalid command")
        docker = shutil.which("docker")
        if docker is None:
            return ToolResult(False, "", "sandbox unavailable: Docker CLI not found")

        # Run on an ephemeral copy. The mount remains read-only; common secret
        # files and credential directories never enter the disposable copy.
        copy_and_run = r"""
import os
import pathlib
import shutil
import subprocess
import sys

src = pathlib.Path("/source")
dst = pathlib.Path("/tmp/forge-workspace")
ignored_dirs = {
    ".git", ".forge", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", ".tox", ".aws", ".ssh", ".kube",
}
protected_names = {
    ".env", "id_rsa", "id_ed25519", ".git-credentials", "credentials.json",
    "secrets.json",
}
protected_suffixes = (".pem", ".key", ".p12", ".pfx")


def ignore(_directory, names):
    blocked = []
    for name in names:
        lowered = name.casefold()
        if lowered in ignored_dirs or lowered in protected_names:
            blocked.append(name)
        elif lowered.startswith(".env.") and lowered != ".env.example":
            blocked.append(name)
        elif lowered.endswith(protected_suffixes):
            blocked.append(name)
        elif "credentials" in lowered or "secrets" in lowered:
            blocked.append(name)
    return blocked


shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore)
env = {
    k: v for k, v in os.environ.items()
    if k in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP"}
}
env["PYTHONDONTWRITEBYTECODE"] = "1"
result = subprocess.run(sys.argv[1:], cwd=dst, env=env, check=False)
sys.exit(result.returncode)
"""
        container_command = [
            docker, "run", "--rm",
            "--network=none",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--read-only",
            "--pids-limit", str(self.pids_limit),
            "--memory", self.memory,
            "--cpus", self.cpus,
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m",
            "--mount", f"type=bind,src={self.workspace},dst=/source,readonly",
            "--workdir", "/tmp",
            self.image,
            "python", "-c", copy_and_run, *command,
        ]
        try:
            proc = subprocess.run(
                container_command,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(False, "", "sandbox command timed out")
        except OSError as exc:
            return ToolResult(False, "", f"sandbox launch failed: {exc}")

        output = (proc.stdout + proc.stderr).strip()
        return ToolResult(
            proc.returncode == 0,
            output[-20_000:],
            metadata={
                "returncode": proc.returncode,
                "sandbox": True,
                "image": self.image,
                "network": "none",
                "read_only_source": True,
                "secret_filtering": True,
                "memory": self.memory,
                "cpus": self.cpus,
            },
        )
