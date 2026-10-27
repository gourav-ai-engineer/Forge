from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .types import RunReport


class RunStore:
    """Small append-only JSON state store for resumable/auditable local runs."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, report: RunReport) -> Path:
        path = self.root / f"{report.task_id}.json"
        path.write_text(json.dumps(asdict(report), indent=2, default=str), encoding="utf-8")
        return path

    def load(self, task_id: str) -> dict:
        path = self.root / f"{task_id}.json"
        if not path.exists():
            raise FileNotFoundError(task_id)
        return json.loads(path.read_text(encoding="utf-8"))
