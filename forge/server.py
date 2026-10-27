from __future__ import annotations

import hmac
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .engine import ForgeEngine
from .providers import provider_from_env
from .types import ForgeTask

logger = logging.getLogger("forge.api")
app = FastAPI(
    title="Forge — Autonomous AI Software Engineer",
    version="0.3.0",
    description="Read-only repository inspection and agent-run reporting API.",
    docs_url="/docs",
    redoc_url=None,
)


class RunRequest(BaseModel):
    request: str = Field(min_length=1, max_length=10_000)


def _authorize(api_key: str | None) -> None:
    expected = os.getenv("FORGE_API_KEY")
    if expected and (api_key is None or not hmac.compare_digest(api_key, expected)):
        raise HTTPException(status_code=401, detail="invalid API key")


def _workspace_root() -> Path:
    root = Path(os.environ.get("FORGE_WORKSPACE", Path.cwd())).resolve()
    allowed_value = os.getenv("FORGE_ALLOWED_ROOT")
    if not allowed_value:
        return root
    allowed = Path(allowed_value).resolve()
    if root != allowed and allowed not in root.parents:
        raise HTTPException(status_code=403, detail="configured workspace is outside allowed root")
    return root


def _run(request: RunRequest) -> dict:
    root = _workspace_root()
    planner = provider_from_env()
    report = ForgeEngine(planner=planner).run(
        ForgeTask(request=request.request.strip(), repo_path=str(root)),
        allow_writes=False,
    )
    return {
        "task_id": report.task_id,
        "status": report.status.value,
        "summary": report.summary,
        "steps": [
            {
                "index": step.index,
                "tool": step.tool,
                "ok": step.ok,
                "output": step.output,
                "duration_ms": round(step.duration_ms, 2),
            }
            for step in report.steps
        ],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "forge"}


@app.post("/run")
@app.post("/api/v1/tasks")
def run_task(payload: RunRequest, x_api_key: str | None = Header(default=None)) -> dict:
    _authorize(x_api_key)
    if not payload.request.strip():
        raise HTTPException(status_code=422, detail="request must not be blank")
    try:
        return _run(payload)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Forge API run failed")
        raise HTTPException(status_code=500, detail="internal server error") from None


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"} and not os.getenv("FORGE_API_KEY"):
        raise RuntimeError("FORGE_API_KEY must be set before exposing the API on a non-local host")
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")
