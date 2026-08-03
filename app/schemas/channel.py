"""Esquemas de respuesta para canales y sus métricas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.channel import ChannelStatus, ChannelType
from app.schemas.pagination import PageMetadata


class ChannelRead(BaseModel):
    """Representación pública de un canal registrado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: str
    external_id: str
    name: str
    category: str | None
    category_id: str | None
    category_name: str | None
    channel_type: ChannelType
    event_start_at: datetime | None
    event_end_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    active: bool
    inactive_since_at: datetime | None
    archived_at: datetime | None
    source_updated_at: datetime | None
    current_server_id: int | None
    event_id: int | None
    technical_stream_id: int | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ChannelMetricRead(BaseModel):
    """Muestra histórica de métricas de un canal."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int
    event_id: int | None
    technical_stream_id: int | None
    server_id: int | None
    collected_at: datetime
    viewers: int
    bitrate_mbps: float | None
    estimated_output_mbps: float | None
    status: ChannelStatus


class ChannelListItem(ChannelRead):
    """Canal junto con servidor asignado y última muestra."""

    current_server_name: str | None = None
    event_external_id: str | None = None
    event_name: str | None = None
    technical_stream_external_id: str | None = None
    technical_stream_name: str | None = None
    latest_metric: ChannelMetricRead | None = None
    viewers: int | None = None
    bitrate_mbps: float | None = None
    estimated_output_mbps: float | None = None
    status: ChannelStatus | None = None
    last_updated_at: datetime | None = None


class ChannelPage(PageMetadata):
    """Página de inventario de canales."""

    items: list[ChannelListItem]
