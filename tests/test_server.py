from __future__ import annotations

from fastapi.testclient import TestClient

from forge.server import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "forge"}


def test_api_key_protects_run_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FORGE_API_KEY", "test-secret")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("FORGE_ALLOWED_ROOT", str(tmp_path))
    client = TestClient(app)

    denied = client.post("/run", json={"request": "inspect"})
    allowed = client.post(
        "/api/v1/tasks",
        json={"request": "inspect this workspace"},
        headers={"X-API-Key": "test-secret"},
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "succeeded"
