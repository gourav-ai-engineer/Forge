from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from forge.tools import ToolRegistry
from forge.types import ToolCall
from forge.workspace import Workspace


def test_python_validation_clears_stale_bytecode_after_same_size_edit(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FORGE_ALLOW_UNSANDBOXED_TESTS", "1")
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'bytecode-fixture'\n"
        "[tool.pytest.ini_options]\ntestpaths = ['.']\n",
        encoding="utf-8",
    )
    calculator = tmp_path / "calculator.py"
    calculator.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (tmp_path / "test_calculator.py").write_text(
        "from calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )

    baseline = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert baseline.returncode != 0
    cache_dir = tmp_path / "__pycache__"
    assert cache_dir.exists(), "baseline should create a Python bytecode cache"

    old_mtime = calculator.stat().st_mtime
    repaired = "def add(a, b):\n    return a + b\n"
    assert len(repaired) == len(calculator.read_text(encoding="utf-8"))
    calculator.write_text(repaired, encoding="utf-8")
    # Reproduce the timestamp+size condition under which CPython can consider an
    # old .pyc valid even though source contents changed.
    os.utime(calculator, (old_mtime, old_mtime))

    result = ToolRegistry(Workspace(tmp_path), allow_writes=True).execute(ToolCall("run_tests"))

    assert result.ok, result.error or result.output
    assert "1 passed" in result.output
    assert not cache_dir.exists()
