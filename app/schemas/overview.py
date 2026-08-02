"""Esquemas del resumen global de la infraestructura."""

from datetime import datetime

from pydantic import BaseModel


class ServerUtilization(BaseModel):
    """Utilización de red de un servidor según su última muestra."""

    server_id: int
    name: str
    output_mbps: float
    network_capacity_mbps: float | None
    # None cuando la capacidad es desconocida o cero (no se puede calcular).
    utilization_percent: float | None


class TopOutputServer(BaseModel):
    """Servidor con mayor salida de red en la última muestra."""

    server_id: int
    name: str
    output_mbps: float


class TopChannel(BaseModel):
    """Canal destacado por número de espectadores en su última muestra."""

    channel_id: int
    name: str
    viewers: int
    collected_at: datetime


class OverviewHistoryPoint(BaseModel):
    """Agregado histórico de una ventana común de recolección."""

    collected_at: datetime
    avg_cpu_percent: float | None
    avg_memory_percent: float | None
    avg_disk_percent: float | None
    total_input_mbps: float
    total_output_mbps: float


class OverviewRead(BaseModel):
    """Resumen agregado del estado actual de la infraestructura.

    Todos los agregados se calculan sobre la muestra más reciente de cada
    servidor o canal habilitado.
    """

    generated_at: datetime
    enabled_servers: int
    total_active_connections: int
    total_output_mbps: float
    total_input_mbps: float
    avg_cpu_percent: float | None
    avg_memory_percent: float | None
    avg_disk_percent: float | None
    channel_count: int
    top_output_server: TopOutputServer | None
    server_network_utilization: list[ServerUtilization]
    top_channels: list[TopChannel]
    history: list[OverviewHistoryPoint]
