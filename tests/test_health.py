"""Tests del healthcheck."""

from app.core.config import get_settings


def test_health_ok(client):
    """El healthcheck reporta aplicación, base de datos y versión."""
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["version"] == get_settings().app_version
