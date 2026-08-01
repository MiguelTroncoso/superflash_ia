"""Esquemas de respuesta para canales y sus métricas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.channel import ChannelStatus
from app.schemas.pagination import PageMetadata


class ChannelRead(BaseModel):
    """Representación pública de un canal registrado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    name: str
    category: str | None
    current_server_id: int | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ChannelMetricRead(BaseModel):
    """Muestra histórica de métricas de un canal."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int
    server_id: int | None
    collected_at: datetime
    viewers: int
    bitrate_mbps: float | None
    estimated_output_mbps: float | None
    status: ChannelStatus


class ChannelListItem(ChannelRead):
    """Canal junto con servidor asignado y última muestra."""

    current_server_name: str | None = None
    latest_metric: ChannelMetricRead | None = None
    viewers: int | None = None
    bitrate_mbps: float | None = None
    estimated_output_mbps: float | None = None
    status: ChannelStatus | None = None
    last_updated_at: datetime | None = None


class ChannelPage(PageMetadata):
    """Página de inventario de canales."""

    items: list[ChannelListItem]
