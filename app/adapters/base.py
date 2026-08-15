"""Contrato que debe cumplir toda fuente de datos de monitoreo.

Los adaptadores devuelven *snapshots* Pydantic — validados en la
frontera del sistema — en lugar de modelos ORM, de modo que la capa de
persistencia quede desacoplada de la fuente concreta (mock hoy, panel
real en el futuro).
"""

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.channel import ChannelStatus, ChannelType
from app.models.server import ServerRole


class ServerSnapshot(BaseModel):
    """Datos de inventario de un servidor según la fuente externa."""

    external_id: str
    name: str
    hostname: str | None = None
    role: ServerRole = ServerRole.OTHER
    network_capacity_mbps: float | None = Field(default=None, ge=0)
    enabled: bool = True


class ServerMetricSnapshot(BaseModel):
    """Muestra de métricas de un servidor entregada por la fuente."""

    server_external_id: str
    collected_at: datetime
    cpu_percent: float = Field(ge=0, le=100)
    memory_percent: float = Field(ge=0, le=100)
    # Opcional: solo las fuentes de infraestructura granulares lo entregan.
    disk_percent: float | None = Field(default=None, ge=0, le=100)
    filesystem_percent: float | None = Field(default=None, ge=0, le=100)
    swap_percent: float | None = Field(default=None, ge=0, le=100)
    input_mbps: float = Field(ge=0)
    output_mbps: float = Field(ge=0)
    io_read_mbps: float | None = Field(default=None, ge=0)
    io_write_mbps: float | None = Field(default=None, ge=0)
    load_average_1m: float | None = Field(default=None, ge=0)
    load_average_5m: float | None = Field(default=None, ge=0)
    load_average_15m: float | None = Field(default=None, ge=0)
    active_connections: int = Field(ge=0)
    active_streams: int = Field(ge=0)
    uptime_seconds: int | None = Field(default=None, ge=0)
    # Permite conservar la fuente efectiva cuando un adapter compuesto mezcla
    # Prometheus real con fallback MOCK por servidor.
    source: str | None = None


class ChannelSnapshot(BaseModel):
    """Datos de inventario de un canal según la fuente externa.

    ``source_id`` permite que dos fuentes usen el mismo ``external_id`` sin
    colisionar. Los campos de evento y stream son opcionales para conservar
    compatibilidad con adapters que solo conocen canales permanentes.
    """

    external_id: str
    name: str
    source_id: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = None
    category_id: str | None = Field(default=None, max_length=100)
    server_external_id: str | None = None
    channel_type: ChannelType = ChannelType.PERMANENT
    event_external_id: str | None = Field(default=None, max_length=200)
    event_name: str | None = Field(default=None, max_length=200)
    event_start_at: datetime | None = None
    event_end_at: datetime | None = None
    technical_stream_external_id: str | None = Field(default=None, max_length=200)
    technical_stream_name: str | None = Field(default=None, max_length=200)
    source_updated_at: datetime | None = None
    enabled: bool = True


class ChannelMetricSnapshot(BaseModel):
    """Muestra de métricas de un canal entregada por la fuente."""

    channel_external_id: str
    source_id: str | None = Field(default=None, min_length=1, max_length=120)
    server_external_id: str | None = None
    event_external_id: str | None = Field(default=None, max_length=200)
    technical_stream_external_id: str | None = Field(default=None, max_length=200)
    collected_at: datetime
    viewers: int = Field(ge=0)
    bitrate_mbps: float | None = Field(default=None, ge=0)
    estimated_output_mbps: float | None = Field(default=None, ge=0)
    status: ChannelStatus = ChannelStatus.UNKNOWN


class MonitoringSourceAdapter(ABC):
    """Interfaz de solo lectura hacia una fuente de datos de monitoreo.

    Las implementaciones NUNCA deben modificar la fuente: este contrato
    es exclusivamente de consulta.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Identificador de la fuente (se persiste en ``ServerMetric.source``)."""

    @abstractmethod
    def get_servers(self) -> list[ServerSnapshot]:
        """Devuelve el inventario actual de servidores."""

    @abstractmethod
    def get_server_metrics(self) -> list[ServerMetricSnapshot]:
        """Devuelve una muestra de métricas por servidor."""

    @abstractmethod
    def get_channels(self) -> list[ChannelSnapshot]:
        """Devuelve el inventario actual de canales."""

    @abstractmethod
    def get_channel_metrics(self) -> list[ChannelMetricSnapshot]:
        """Devuelve una muestra de métricas por canal."""

    def begin_collection_cycle(self) -> None:
        """Señala el inicio de una pasada de recolección.

        Los adaptadores que cachean una muestra por ciclo (p. ej. el
        compuesto) la invalidan aquí para garantizar datos frescos y
        consistentes dentro de la pasada. Por defecto no hace nada.
        """
        return None
