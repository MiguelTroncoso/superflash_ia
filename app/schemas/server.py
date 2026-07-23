"""Esquemas de respuesta para servidores y sus métricas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.server import ServerRole


class ServerRead(BaseModel):
    """Representación pública de un servidor registrado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    name: str
    hostname: str | None
    role: ServerRole
    network_capacity_mbps: float | None
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
    input_mbps: float
    output_mbps: float
    active_connections: int
    active_streams: int
    uptime_seconds: int | None
    source: str
