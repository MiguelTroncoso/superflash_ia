"""Configuración central basada en Pydantic Settings.

Todos los valores sensibles (credenciales, URLs privadas) llegan por
variables de entorno o por el archivo local ``.env`` — nunca se
versionan en el repositorio.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Adaptador de monitoreo activo. Cuando exista una fuente real se
    # añadirá aquí su identificador (p. ej. "panel") sin tocar el resto.
    monitoring_adapter: Literal["mock"] = "mock"
    mock_seed: int = 42

    # Lista de orígenes CORS permitidos. Vacía = middleware CORS apagado.
    cors_origins: list[str] = Field(default_factory=list)

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
