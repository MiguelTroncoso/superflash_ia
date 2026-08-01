"""Contratos del balance de utilización de infraestructura."""

from datetime import datetime

from pydantic import BaseModel


class BalanceServerRead(BaseModel):
    """Balance de un servidor con muestra disponible."""

    server_id: int
    name: str
    output_mbps: float
    capacity_mbps: float | None
    utilization_percent: float | None


class BalanceRead(BaseModel):
    """Agregados de capacidad y utilización de servidores habilitados."""

    generated_at: datetime
    server_count: int
    sampled_server_count: int
    average_cpu_percent: float | None
    average_memory_percent: float | None
    average_network_mbps: float | None
    average_network_utilization_percent: float | None
    average_disk_percent: float | None
    capacity_total_mbps: float
    capacity_used_mbps: float
    capacity_free_mbps: float
    most_loaded: BalanceServerRead | None
    least_utilized: BalanceServerRead | None
    servers: list[BalanceServerRead]
