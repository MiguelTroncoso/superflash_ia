"""Tests de autenticación global: todos los /api/v1 exigen X-API-Key."""

import pytest

from tests.conftest import TEST_API_KEY

PROTECTED_GETS = [
    "/api/v1/servers",
    "/api/v1/channels",
    "/api/v1/overview",
    "/api/v1/collection/status",
    "/api/v1/alerts",
]


@pytest.mark.parametrize("path", PROTECTED_GETS)
def test_get_endpoints_reject_missing_key(anon_client, path):
    """Sin cabecera X-API-Key cualquier GET de la v1 responde 401."""
    assert anon_client.get(path).status_code == 401


@pytest.mark.parametrize("path", PROTECTED_GETS)
def test_get_endpoints_reject_wrong_key(anon_client, path):
    """Una clave incorrecta también es rechazada."""
    assert anon_client.get(path, headers={"X-API-Key": "clave-mala"}).status_code == 401


@pytest.mark.parametrize("path", PROTECTED_GETS)
def test_get_endpoints_accept_valid_key(anon_client, path):
    """Con la clave correcta todos los GET responden 200."""
    assert anon_client.get(path, headers={"X-API-Key": TEST_API_KEY}).status_code == 200


def test_health_remains_public(anon_client):
    """/health sigue siendo público (para orquestadores y healthchecks)."""
    response = anon_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
