"""Configuración central basada en Pydantic Settings.

Todos los valores sensibles (credenciales, claves de API) llegan por
variables de entorno o por el archivo local ``.env`` — nunca se
versionan en el repositorio.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
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
    # diagnóstico. Fuentes reales adicionales (netdata, panel...) se
    # registrarán como nuevos valores en app/adapters/factory.py.
    infrastructure_source: Literal["mock", "prometheus"] = "mock"
    streaming_source: Literal["mock"] = "mock"

    # --- Fuente de infraestructura: Prometheus (node_exporter) ---
    # URL base del servidor Prometheus (solo se hacen GET de consulta).
    prometheus_url: str | None = None
    prometheus_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    # Token opcional (cabecera Authorization: Bearer ...). Nunca se loguea.
    prometheus_bearer_token: str | None = None
    # Verificación TLS activada por defecto; en producción no puede
    # desactivarse (ver validador más abajo).
    prometheus_tls_verify: bool = True
    # Inventario local de servidores (YAML o JSON, NO versionado).
    # Ejemplo sin datos reales: config/inventory.example.yaml
    infrastructure_inventory_file: str | None = None

    # SSH onboarding: credentials are accepted only for the in-memory job and
    # host keys are verified against this operator-managed file.
    ssh_known_hosts_file: str = "/etc/ssh/ssh_known_hosts"
    ssh_connect_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    ssh_command_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    ssh_retry_count: int = Field(default=2, ge=0, le=5)
    onboarding_monitor_ip: str = "178.104.98.19"
    node_exporter_version: str | None = None
    onboarding_enabled: bool = True

    # Clave requerida por TODOS los endpoints /api/v1 (cabecera X-API-Key).
    # Sin clave configurada, la API se niega a operar (fail-closed).
    # Se acepta el nombre histórico COLLECTION_API_KEY como alias.
    api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("api_key", "collection_api_key")
    )

    # Programador de recolección periódica. Deshabilitado por defecto.
    scheduler_enabled: bool = False
    collection_interval_seconds: int = Field(default=300, ge=5)

    # Una recolección se considera abandonada solo cuando su heartbeat
    # supera este plazo (proceso interrumpido sin completar el registro).
    collection_timeout_seconds: int = Field(default=600, ge=30)

    # Retención de histórico (métricas y ejecuciones). None = deshabilitada;
    # la limpieza jamás corre sin este valor configurado explícitamente.
    metrics_retention_days: int | None = Field(default=None, ge=1)

    # Retención del inventario dinámico de canales/eventos. Los canales se
    # marcan inactivos de inmediato; estas ventanas controlan cuándo pueden
    # pasar a archivados.
    event_inactive_grace_hours: int = Field(default=6, ge=0, le=24 * 30)
    event_archive_days: int = Field(default=7, ge=1, le=3650)
    permanent_archive_days: int = Field(default=30, ge=1, le=3650)

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

    @model_validator(mode="after")
    def _forbid_insecure_tls_in_production(self) -> "Settings":
        """En producción la verificación TLS de Prometheus es obligatoria."""
        if self.app_env == "production" and not self.prometheus_tls_verify:
            raise ValueError("PROMETHEUS_TLS_VERIFY=false no está permitido con APP_ENV=production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración cacheada (una sola lectura del entorno)."""
    return Settings()
