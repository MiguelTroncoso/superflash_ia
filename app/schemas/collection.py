"""Esquemas del resultado, historial y estado de la recolección."""

from datetime import datetime

from pydantic import BaseModel, Field

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


class CollectionStatusRead(BaseModel):
    """Contrato estable de ``GET /api/v1/collection/status``.

    Describe la ejecución relevante: la que está en curso si la hay, o la
    última terminada. Los campos provienen del historial persistido
    (``collection_runs``), por lo que el estado es visible desde
    cualquier instancia y sobrevive a reinicios. Una fila ``running``
    solo cuenta como en curso si su ``heartbeat_at`` no superó
    ``COLLECTION_TIMEOUT_SECONDS``.

    ``inserted`` y ``skipped`` agregan métricas de servidores y canales.
    ``next_run_at`` es el próximo ciclo del scheduler (null si está
    apagado o la consulta llega a una instancia sin scheduler).
    """

    running: bool
    run_id: int | None = None
    source: str | None = None
    triggered_by: CollectionTrigger | None = None
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    status: CollectionRunStatus | None = None
    inserted: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    next_run_at: datetime | None = None
