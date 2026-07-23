"""Configuración central basada en Pydantic Settings.

Todos los valores sensibles (credenciales, claves de API) llegan por
variables de entorno o por el archivo local ``.env`` — nunca se
versionan en el repositorio.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
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

    # Adaptador de monitoreo activo. Cuando exista una fuente real se
    # añadirá aquí su identificador (p. ej. "panel") sin tocar el resto.
    monitoring_adapter: Literal["mock"] = "mock"
    mock_seed: int = 42

    # Clave requerida por los endpoints internos (POST /api/v1/collection/run).
    # Sin clave configurada, esos endpoints se niegan a operar (fail-closed).
    collection_api_key: str | None = None

    # Programador de recolección periódica. Deshabilitado por defecto.
    scheduler_enabled: bool = False
    collection_interval_seconds: int = Field(default=300, ge=5)

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
