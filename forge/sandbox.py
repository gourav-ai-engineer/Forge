from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .types import ToolResult


class SandboxRunner:
    """Run validation commands inside a hardened, disposable Docker container."""

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
        self.image = image or os.getenv("FORGE_SANDBOX_IMAGE", "python:3.12-slim")
        self.memory = memory
        self.cpus = cpus
        self.pids_limit = pids_limit

    def run(self, command: list[str], timeout_seconds: int = 180) -> ToolResult:
        if not command or any("\x00" in part for part in command):
            return ToolResult(False, "", "invalid command")
        docker = shutil.which("docker")
        if docker is None:
            return ToolResult(False, "", "sandbox unavailable: Docker CLI not found")

        container_command = [
            docker,
            "run",
            "--rm",
            "--network=none",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--read-only",
            "--pids-limit",
            str(self.pids_limit),
            "--memory",
            self.memory,
            "--cpus",
            self.cpus,
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,noexec,size=128m",
            "--mount",
            f"type=bind,src={self.workspace},dst=/workspace,rw",
            "--workdir",
            "/workspace",
            self.image,
            *command,
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
                "memory": self.memory,
                "cpus": self.cpus,
            },
        )
