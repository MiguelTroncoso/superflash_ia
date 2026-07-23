"""Tests de la configuración (parsing de variables de entorno)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_cors_origins_empty_string(monkeypatch):
    """CORS_ORIGINS vacío (como en .env.example) no debe romper el arranque."""
    monkeypatch.setenv("CORS_ORIGINS", "")
    assert Settings(_env_file=None).cors_origins == []


def test_cors_origins_comma_separated(monkeypatch):
    """CORS_ORIGINS admite lista separada por comas con espacios."""
    monkeypatch.setenv("CORS_ORIGINS", "http://a.local, http://b.local")
    assert Settings(_env_file=None).cors_origins == ["http://a.local", "http://b.local"]


def test_scheduler_disabled_by_default(monkeypatch):
    """El scheduler nunca debe activarse sin decisión explícita."""
    monkeypatch.delenv("SCHEDULER_ENABLED", raising=False)
    monkeypatch.delenv("COLLECTION_INTERVAL_SECONDS", raising=False)
    settings = Settings(_env_file=None)
    assert settings.scheduler_enabled is False
    assert settings.collection_interval_seconds == 300


def test_collection_api_key_unset_by_default(monkeypatch):
    """Sin variable de entorno no existe clave (el endpoint queda fail-closed)."""
    monkeypatch.delenv("COLLECTION_API_KEY", raising=False)
    assert Settings(_env_file=None).collection_api_key is None


def test_interval_minimum_enforced():
    """Intervalos absurdamente bajos se rechazan en la configuración."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, collection_interval_seconds=1)
