from __future__ import annotations

from pathlib import Path

from forge.engine import ForgeEngine
from forge.types import ForgeTask


def test_failed_validation_output_is_preserved_for_recovery(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FORGE_ALLOW_UNSANDBOXED_TESTS", "1")
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'failure-output-fixture'\n"
        "[tool.pytest.ini_options]\ntestpaths = ['.']\n",
        encoding="utf-8",
    )
    (tmp_path / "test_expected_failure.py").write_text(
        "def test_expected_failure():\n    assert 1 == 2\n",
        encoding="utf-8",
    )

    report = ForgeEngine().run(
        ForgeTask(request="Inspect and validate the fixture", repo_path=str(tmp_path))
    )
    validations = [step for step in report.steps if step.tool == "run_tests"]

    assert validations
    assert not validations[-1].ok
    assert "assert 1 == 2" in validations[-1].output
    assert "AssertionError" in validations[-1].output
