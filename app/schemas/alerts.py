"""Esquemas de las alertas internas de solo lectura."""

import enum
from datetime import datetime

from pydantic import BaseModel

from app.models.alert import AlertSeverity, AlertStatus


class AlertType(enum.StrEnum):
    """Tipos de alerta evaluados sobre la última muestra de cada servidor."""

    HIGH_CPU = "high_cpu"
    HIGH_MEMORY = "high_memory"
    HIGH_DISK = "high_disk"
    HIGH_NETWORK_UTILIZATION = "high_network_utilization"
    STALE_SERVER = "stale_server"


class AlertRead(BaseModel):
    """Una alerta activa sobre un servidor."""

    id: int | None = None
    type: AlertType
    severity: AlertSeverity = AlertSeverity.WARNING
    status: AlertStatus = AlertStatus.ACTIVE
    server_id: int
    server_name: str
    message: str
    # Valor observado y umbral configurado (None cuando no aplican,
    # p. ej. un servidor sin ninguna muestra registrada).
    value: float | None = None
    threshold: float | None = None
    collected_at: datetime | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None


class AlertsRead(BaseModel):
    """Respuesta de GET /api/v1/alerts (evaluación bajo demanda)."""

    generated_at: datetime
    alerts: list[AlertRead]


class AlertUpdate(BaseModel):
    """Cambio permitido en el ciclo de vida de una alerta."""

    status: AlertStatus
