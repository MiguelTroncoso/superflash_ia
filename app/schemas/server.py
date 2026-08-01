"""Esquemas de respuesta para servidores y sus métricas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.server import ServerOperationalStatus, ServerRole
from app.schemas.pagination import PageMetadata


class ServerFields(BaseModel):
    """Campos administrables del inventario de servidores."""

    external_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    hostname: str | None = Field(default=None, max_length=255)
    role: ServerRole = ServerRole.OTHER
    provider: str | None = Field(default=None, max_length=120)
    datacenter: str | None = Field(default=None, max_length=120)
    group: str | None = Field(default=None, max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=50)
    type: str | None = Field(default=None, max_length=80)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    network_speed_mbps: float | None = Field(default=None, ge=0)
    prometheus_url: str | None = Field(default=None, max_length=500)
    prometheus_token: str | None = Field(default=None, max_length=1000)
    heartbeat_interval_seconds: int = Field(default=300, ge=30, le=86_400)
    status: ServerOperationalStatus = ServerOperationalStatus.UNKNOWN
    notes: str | None = Field(default=None, max_length=2000)
    enabled: bool = True

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class ServerCreate(ServerFields):
    """Payload para crear un servidor de inventario."""


class ServerUpdate(BaseModel):
    """Payload parcial para actualizar un servidor."""

    external_id: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    hostname: str | None = Field(default=None, max_length=255)
    role: ServerRole | None = None
    provider: str | None = Field(default=None, max_length=120)
    datacenter: str | None = Field(default=None, max_length=120)
    group: str | None = Field(default=None, max_length=120)
    tags: list[str] | None = Field(default=None, max_length=50)
    type: str | None = Field(default=None, max_length=80)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    network_speed_mbps: float | None = Field(default=None, ge=0)
    prometheus_url: str | None = Field(default=None, max_length=500)
    prometheus_token: str | None = Field(default=None, max_length=1000)
    heartbeat_interval_seconds: int | None = Field(default=None, ge=30, le=86_400)
    status: ServerOperationalStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)
    enabled: bool | None = None

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class ServerRead(BaseModel):
    """Representación pública de un servidor registrado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    name: str
    hostname: str | None
    role: ServerRole
    provider: str | None
    datacenter: str | None
    group: str | None
    tags: list[str]
    type: str | None
    country: str | None
    network_capacity_mbps: float | None
    network_speed_mbps: float | None
    prometheus_configured: bool
    heartbeat_interval_seconds: int
    last_heartbeat_at: datetime | None
    status: ServerOperationalStatus
    notes: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ServerMetricRead(BaseModel):
    """Muestra histórica de métricas de un servidor."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    server_id: int
    collected_at: datetime
    cpu_percent: float
    memory_percent: float
    disk_percent: float | None
    filesystem_percent: float | None
    swap_percent: float | None
    input_mbps: float
    output_mbps: float
    io_read_mbps: float | None
    io_write_mbps: float | None
    load_average_1m: float | None
    load_average_5m: float | None
    load_average_15m: float | None
    active_connections: int
    active_streams: int
    uptime_seconds: int | None
    source: str


class ServerListItem(ServerRead):
    """Servidor junto con su última muestra y resumen operativo."""

    latest_metric: ServerMetricRead | None = None
    network_utilization_percent: float | None = None
    active_alert_count: int = Field(ge=0)
    last_updated_at: datetime | None = None


class ServerPage(PageMetadata):
    """Página de inventario de servidores."""

    items: list[ServerListItem]
