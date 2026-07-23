"""Contratos separados por tipo de fuente de monitoreo.

La interfaz histórica ``MonitoringSourceAdapter`` (``base.py``) combina
infraestructura y streaming en un solo contrato. Las fuentes reales rara
vez funcionan así: las métricas de máquina suelen venir de un sistema
(Prometheus, Netdata, API del proveedor) y las de audiencia de otro (API
del panel de streaming). Estos contratos permiten integrar cada fuente
por separado; ``CompositeMonitoringAdapter`` los une hacia el pipeline
de persistencia existente.

Todas las implementaciones son de SOLO LECTURA: consultar, nunca
modificar la fuente. Ver docs/real-source-integration.md.
"""

import enum
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field

from app.adapters.base import ChannelSnapshot, ServerSnapshot
from app.models.channel import ChannelStatus


class ServerStatus(enum.StrEnum):
    """Estado operativo de un servidor según la fuente de infraestructura.

    Aún no se persiste en la base de datos; queda disponible en el
    snapshot para diagnóstico y para una futura migración.
    """

    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class InfrastructureMetricSnapshot(BaseModel):
    """Muestra de métricas de máquina entregada por una fuente de infraestructura."""

    server_external_id: str
    collected_at: datetime
    cpu_percent: float = Field(ge=0, le=100)
    memory_percent: float = Field(ge=0, le=100)
    disk_percent: float | None = Field(default=None, ge=0, le=100)
    input_mbps: float = Field(ge=0)
    output_mbps: float = Field(ge=0)
    load_average_1m: float | None = Field(default=None, ge=0)
    load_average_5m: float | None = Field(default=None, ge=0)
    load_average_15m: float | None = Field(default=None, ge=0)
    uptime_seconds: int | None = Field(default=None, ge=0)
    status: ServerStatus = ServerStatus.UNKNOWN


class StreamingChannelMetricSnapshot(BaseModel):
    """Muestra de métricas de audiencia entregada por una fuente de streaming."""

    channel_external_id: str
    server_external_id: str | None = None
    collected_at: datetime
    viewers: int = Field(ge=0)
    bitrate_mbps: float | None = Field(default=None, ge=0)
    status: ChannelStatus = ChannelStatus.UNKNOWN


class InfrastructureMetricsAdapter(ABC):
    """Fuente de solo lectura de métricas de máquina (CPU, RAM, disco, red)."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Identificador de la fuente (p. ej. ``mock-infra``, ``prometheus``)."""

    @abstractmethod
    def get_servers(self) -> list[ServerSnapshot]:
        """Inventario de servidores conocidos por esta fuente."""

    @abstractmethod
    def get_infrastructure_metrics(self) -> list[InfrastructureMetricSnapshot]:
        """Una muestra de métricas de máquina por servidor."""


class StreamingMetricsAdapter(ABC):
    """Fuente de solo lectura de métricas de canales/streaming."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Identificador de la fuente (p. ej. ``mock-streaming``, ``panel``)."""

    @abstractmethod
    def get_channels(self) -> list[ChannelSnapshot]:
        """Inventario de canales conocidos por esta fuente."""

    @abstractmethod
    def get_streaming_metrics(self) -> list[StreamingChannelMetricSnapshot]:
        """Una muestra de métricas de audiencia por canal."""
