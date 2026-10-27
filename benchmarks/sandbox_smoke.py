from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from forge.sandbox import SandboxRunner


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="forge-sandbox-smoke-") as raw_root:
        root = Path(raw_root)
        (root / "pyproject.toml").write_text(
            "[project]\nname = 'forge-sandbox-smoke'\n"
            "[tool.pytest.ini_options]\ntestpaths = ['.']\n",
            encoding="utf-8",
        )
        (root / "test_sandbox_smoke.py").write_text(
            "from pathlib import Path\n"
            "def test_sandbox_copy_filters_credentials():\n"
            "    assert not Path('.env').exists()\n"
            "    assert not Path('credentials.json').exists()\n"
            "    assert Path('.env.example').exists()\n"
            "def test_sandbox_command_executes():\n"
            "    assert 2 + 2 == 4\n",
            encoding="utf-8",
        )
        (root / ".env").write_text(
            "OPENAI_API_KEY=should-never-enter-sandbox-copy\n",
            encoding="utf-8",
        )
        (root / "credentials.json").write_text(
            '{"token":"should-never-enter-sandbox-copy"}\n',
            encoding="utf-8",
        )
        (root / ".env.example").write_text("OPENAI_API_KEY=\n", encoding="utf-8")

        result = SandboxRunner(root).run(
            ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            timeout_seconds=90,
        )
        print(json.dumps({
            "sandbox": result.metadata,
            "ok": result.ok,
            "output": result.output,
            "error": result.error,
        }, indent=2))
        return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
