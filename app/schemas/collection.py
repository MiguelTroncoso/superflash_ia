"""Esquemas del resultado y el estado de la recolección."""

from datetime import datetime

from pydantic import BaseModel, Field


class CollectionResult(BaseModel):
    """Resumen de una ejecución del recolector de métricas."""

    adapter: str
    collected_at: datetime
    servers_synced: int = 0
    channels_synced: int = 0
    server_metrics_inserted: int = 0
    server_metrics_skipped: int = 0
    channel_metrics_inserted: int = 0
    channel_metrics_skipped: int = 0
    # Errores no fatales: un fallo puntual no aborta la recolección completa.
    errors: list[str] = Field(default_factory=list)


class CollectionLastRun(BaseModel):
    """Detalle de la última recolección terminada en este proceso."""

    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    success: bool
    error: str | None = None
    result: CollectionResult | None = None


class SchedulerStatus(BaseModel):
    """Estado del programador periódico de recolecciones."""

    enabled: bool
    interval_seconds: float
    next_run_at: datetime | None = None


class CollectionStatusRead(BaseModel):
    """Estado observable del subsistema de recolección."""

    running: bool
    current_run_started_at: datetime | None = None
    last_run: CollectionLastRun | None = None
    scheduler: SchedulerStatus
