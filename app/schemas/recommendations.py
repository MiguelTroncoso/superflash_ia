"""Contratos de recomendaciones deterministas del monitor."""

import enum
from datetime import datetime

from pydantic import BaseModel


class RecommendationSeverity(enum.StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RecommendationType(enum.StrEnum):
    HIGH_CPU = "high_cpu"
    HIGH_MEMORY = "high_memory"
    HIGH_DISK = "high_disk"
    HIGH_NETWORK = "high_network"
    HEARTBEAT_LOST = "heartbeat_lost"
    NO_DATA = "no_data"
    UNDERUTILIZED = "underutilized"


class RecommendationRead(BaseModel):
    """Una recomendación accionable sin ejecutar acciones."""

    type: RecommendationType
    severity: RecommendationSeverity
    server_id: int
    server_name: str
    title: str
    message: str
    value: float | None = None
    threshold: float | None = None
    generated_at: datetime


class RecommendationsRead(BaseModel):
    """Colección de recomendaciones actuales."""

    generated_at: datetime
    recommendations: list[RecommendationRead]
