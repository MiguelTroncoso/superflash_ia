"""Configuración central basada en Pydantic Settings.

Todos los valores sensibles (credenciales, claves de API) llegan por
variables de entorno o por el archivo local ``.env`` — nunca se
versionan en el repositorio.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación, cargada del entorno o de ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SuperFlash Monitor"
    app_version: str = "0.1.0"
    app_env: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://superflash:changeme@localhost:5432/superflash"

    # Adaptador que alimenta la recolección: "mock" (combinado histórico)
    # o "composite" (une las dos fuentes por tipo configuradas abajo).
    monitoring_adapter: Literal["mock", "composite"] = "mock"
    mock_seed: int = 42

    # Fuentes por tipo, usadas por "composite" y por el comando de
    # diagnóstico. Las fuentes reales (prometheus, netdata, panel...) se
    # registrarán como nuevos valores en app/adapters/factory.py.
    infrastructure_source: Literal["mock"] = "mock"
    streaming_source: Literal["mock"] = "mock"

    # Clave requerida por TODOS los endpoints /api/v1 (cabecera X-API-Key).
    # Sin clave configurada, la API se niega a operar (fail-closed).
    # Se acepta el nombre histórico COLLECTION_API_KEY como alias.
    api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("api_key", "collection_api_key")
    )

    # Programador de recolección periódica. Deshabilitado por defecto.
    scheduler_enabled: bool = False
    collection_interval_seconds: int = Field(default=300, ge=5)

    # Retención de histórico (métricas y ejecuciones). None = deshabilitada;
    # la limpieza jamás corre sin este valor configurado explícitamente.
    metrics_retention_days: int | None = Field(default=None, ge=1)

    # Umbrales de las alertas internas de solo lectura (GET /api/v1/alerts).
    alert_cpu_percent: float = Field(default=90.0, gt=0, le=100)
    alert_memory_percent: float = Field(default=90.0, gt=0, le=100)
    alert_disk_percent: float = Field(default=90.0, gt=0, le=100)
    alert_network_utilization_percent: float = Field(default=85.0, gt=0)
    alert_stale_minutes: int = Field(default=15, ge=1)

    # Lista de orígenes CORS permitidos. Vacía = middleware CORS apagado.
    # NoDecode evita que pydantic-settings intente decodificar la variable
    # como JSON: el valor llega crudo al validador y se separa por comas.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Permite definir CORS_ORIGINS como cadena separada por comas."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración cacheada (una sola lectura del entorno)."""
    return Settings()
