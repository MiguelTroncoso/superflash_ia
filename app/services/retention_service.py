"""Política de retención del histórico propio de la plataforma.

Borra únicamente datos de la base de datos de SuperFlash Monitor
(métricas y ejecuciones de recolección más antiguas que el corte).
Nunca toca infraestructura externa. La limpieza jamás se ejecuta sin
``METRICS_RETENTION_DAYS`` configurado explícitamente.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from pydantic import BaseModel
from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.orm import Session

from app.models.channel import ChannelMetric
from app.models.collection_run import CollectionRun
from app.models.server import ServerMetric

logger = logging.getLogger(__name__)


class RetentionResult(BaseModel):
    """Resumen de una pasada de limpieza (o de su simulación)."""

    cutoff: datetime
    dry_run: bool
    server_metrics_deleted: int = 0
    channel_metrics_deleted: int = 0
    collection_runs_deleted: int = 0


def prune_history(session: Session, retention_days: int, dry_run: bool = False) -> RetentionResult:
    """Elimina (o cuenta, con ``dry_run``) el histórico anterior al corte.

    Args:
        session: Sesión de base de datos.
        retention_days: Días de histórico a conservar (>= 1).
        dry_run: Si es True solo cuenta, sin borrar nada.
    """
    if retention_days < 1:
        raise ValueError("retention_days debe ser >= 1")
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    result = RetentionResult(cutoff=cutoff, dry_run=dry_run)

    if dry_run:
        result.server_metrics_deleted = int(
            session.scalar(
                select(func.count())
                .select_from(ServerMetric)
                .where(ServerMetric.collected_at < cutoff)
            )
            or 0
        )
        result.channel_metrics_deleted = int(
            session.scalar(
                select(func.count())
                .select_from(ChannelMetric)
                .where(ChannelMetric.collected_at < cutoff)
            )
            or 0
        )
        result.collection_runs_deleted = int(
            session.scalar(
                select(func.count())
                .select_from(CollectionRun)
                .where(CollectionRun.started_at < cutoff)
            )
            or 0
        )
        return result

    def _delete(statement: Any) -> int:
        return cast("CursorResult[Any]", session.execute(statement)).rowcount

    result.server_metrics_deleted = _delete(
        delete(ServerMetric).where(ServerMetric.collected_at < cutoff)
    )
    result.channel_metrics_deleted = _delete(
        delete(ChannelMetric).where(ChannelMetric.collected_at < cutoff)
    )
    result.collection_runs_deleted = _delete(
        delete(CollectionRun).where(CollectionRun.started_at < cutoff)
    )
    session.commit()
    logger.info(
        "retencion aplicada cutoff=%s server_metrics=%d channel_metrics=%d runs=%d",
        cutoff.isoformat(),
        result.server_metrics_deleted,
        result.channel_metrics_deleted,
        result.collection_runs_deleted,
    )
    return result
