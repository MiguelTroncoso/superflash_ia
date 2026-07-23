"""Esquemas de las alertas internas de solo lectura."""

import enum
from datetime import datetime

from pydantic import BaseModel


class AlertType(enum.StrEnum):
    """Tipos de alerta evaluados sobre la última muestra de cada servidor."""

    HIGH_CPU = "high_cpu"
    HIGH_MEMORY = "high_memory"
    HIGH_DISK = "high_disk"
    HIGH_NETWORK_UTILIZATION = "high_network_utilization"
    STALE_SERVER = "stale_server"


class AlertRead(BaseModel):
    """Una alerta activa sobre un servidor."""

    type: AlertType
    server_id: int
    server_name: str
    message: str
    # Valor observado y umbral configurado (None cuando no aplican,
    # p. ej. un servidor sin ninguna muestra registrada).
    value: float | None = None
    threshold: float | None = None
    collected_at: datetime | None = None


class AlertsRead(BaseModel):
    """Respuesta de GET /api/v1/alerts (evaluación bajo demanda)."""

    generated_at: datetime
    alerts: list[AlertRead]
