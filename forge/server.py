from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .engine import ForgeEngine
from .types import ForgeTask


class ForgeHandler(BaseHTTPRequestHandler):
    server_version = "Forge/0.1"

    def _send(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, {"status": "ok", "service": "forge"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/run":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 50_000:
                raise ValueError("request body too large")
            body = json.loads(self.rfile.read(length) or b"{}")
            request = str(body.get("request", "")).strip()
            workspace_root = Path(os.environ.get("FORGE_WORKSPACE", Path.cwd())).resolve()
            if not request:
                raise ValueError("request is required")
            report = ForgeEngine().run(
                ForgeTask(request=request, repo_path=str(workspace_root)),
                allow_writes=False,
            )
            self._send(200, {
                "task_id": report.task_id,
                "status": report.status,
                "summary": report.summary,
                "steps": [
                    {"index": s.index, "tool": s.tool, "ok": s.ok, "output": s.output,
                     "duration_ms": round(s.duration_ms, 2)} for s in report.steps
                ],
            })
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})
        except Exception:
            self._send(500, {"error": "internal server error"})

    def log_message(self, format: str, *args: object) -> None:
        return


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    ThreadingHTTPServer((host, port), ForgeHandler).serve_forever()
