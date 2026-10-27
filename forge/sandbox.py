from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .types import ToolResult


class SandboxRunner:
    """Run repository validation in a disposable, network-isolated Docker copy."""

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

        # The source repository is mounted read-only. Tests execute on a disposable
        # copy under the container's bounded tmpfs, so test code cannot mutate the
        # user's checkout through the bind mount.
        copy_and_run = (
            "import os, pathlib, shutil, subprocess, sys; "
            "src=pathlib.Path('/source'); dst=pathlib.Path('/tmp/forge-workspace'); "
            "shutil.copytree(src, dst, dirs_exist_ok=True, "
            "ignore=shutil.ignore_patterns('.git','.forge','.venv','venv',"
            "'node_modules','__pycache__','.pytest_cache','.ruff_cache')); "
            "env={k:v for k,v in os.environ.items() if k in "
            "{'PATH','HOME','LANG','LC_ALL','TMPDIR','TEMP','TMP'}}; "
            "env['PYTHONDONTWRITEBYTECODE']='1'; "
            "result=subprocess.run(sys.argv[1:], cwd=dst, env=env, check=False); "
            "sys.exit(result.returncode)"
        )
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
                "memory": self.memory,
                "cpus": self.cpus,
            },
        )
