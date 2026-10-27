from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepositoryProfile:
    root: str
    languages: tuple[str, ...]
    file_count: int
    has_git: bool
    test_command: tuple[str, ...] | None
    build_command: tuple[str, ...] | None


def analyze_repository(root: str | Path) -> RepositoryProfile:
    base = Path(root).resolve()
    files = [p for p in base.rglob("*") if p.is_file() and ".git" not in p.parts]
    suffixes = {p.suffix.lower() for p in files}
    languages: list[str] = []
    if ".py" in suffixes:
        languages.append("python")
    if ".ts" in suffixes or ".tsx" in suffixes:
        languages.append("typescript")
    if ".js" in suffixes or ".jsx" in suffixes:
        languages.append("javascript")
    if ".go" in suffixes:
        languages.append("go")
    if ".rs" in suffixes:
        languages.append("rust")
    if ".cpp" in suffixes or ".cc" in suffixes:
        languages.append("cpp")

    test_command = None
    build_command = None
    if (base / "pyproject.toml").exists() or (base / "pytest.ini").exists() or (base / "tests").exists():
        test_command = ("python", "-m", "pytest", "-q")
    elif (base / "package.json").exists():
        test_command = ("npm", "test", "--", "--runInBand")
    if (base / "pyproject.toml").exists():
        build_command = ("python", "-m", "build")
    elif (base / "package.json").exists():
        build_command = ("npm", "run", "build")

    return RepositoryProfile(
        root=str(base),
        languages=tuple(languages),
        file_count=len(files),
        has_git=(base / ".git").exists(),
        test_command=test_command,
        build_command=build_command,
    )
