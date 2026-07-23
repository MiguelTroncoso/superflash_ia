"""Esquemas del resultado de una ejecución de recolección."""

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
