"""Esquemas de respuesta para canales y sus métricas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.channel import ChannelStatus


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
