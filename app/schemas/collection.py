"""Esquemas del resultado, historial y estado de la recolección."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.collection_run import CollectionRunStatus, CollectionTrigger


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


class CollectionRunRead(BaseModel):
    """Ejecución de recolección persistida en ``collection_runs``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    source: str
    status: CollectionRunStatus
    triggered_by: CollectionTrigger
    servers_synced: int
    channels_synced: int
    server_metrics_inserted: int
    server_metrics_skipped: int
    channel_metrics_inserted: int
    channel_metrics_skipped: int
    errors: list[str]


class SchedulerStatus(BaseModel):
    """Estado del programador periódico de recolecciones."""

    enabled: bool
    interval_seconds: float
    next_run_at: datetime | None = None


class CollectionStatusRead(BaseModel):
    """Estado observable del subsistema de recolección.

    ``last_run`` proviene del historial persistido, por lo que es visible
    desde cualquier instancia y sobrevive a reinicios del proceso.
    """

    running: bool
    current_run_started_at: datetime | None = None
    last_run: CollectionRunRead | None = None
    scheduler: SchedulerStatus
