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


def test_api_key_unset_by_default(monkeypatch):
    """Sin variable de entorno no existe clave (la API queda fail-closed)."""
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("COLLECTION_API_KEY", raising=False)
    assert Settings(_env_file=None).api_key is None


def test_api_key_accepts_legacy_env_name(monkeypatch):
    """El nombre histórico COLLECTION_API_KEY sigue funcionando como alias."""
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("COLLECTION_API_KEY", "clave-legada")
    assert Settings(_env_file=None).api_key == "clave-legada"


def test_retention_disabled_by_default(monkeypatch):
    """La retención jamás se activa sin configuración explícita."""
    monkeypatch.delenv("METRICS_RETENTION_DAYS", raising=False)
    assert Settings(_env_file=None).metrics_retention_days is None


def test_interval_minimum_enforced():
    """Intervalos absurdamente bajos se rechazan en la configuración."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, collection_interval_seconds=1)
