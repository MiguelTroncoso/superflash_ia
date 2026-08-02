"""Acceso a datos del historial de ejecuciones de recolección."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutils import ensure_utc
from app.models.collection_run import CollectionRun, CollectionRunStatus, CollectionTrigger
from app.schemas.collection import CollectionResult


class CollectionRunRepository:
    """Consultas y persistencia sobre ``CollectionRun``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def start(
        self, source: str, started_at: datetime, triggered_by: CollectionTrigger
    ) -> CollectionRun:
        """Registra el inicio de una ejecución (estado ``running``)."""
        run = CollectionRun(
            started_at=started_at,
            heartbeat_at=started_at,
            source=source,
            status=CollectionRunStatus.RUNNING,
            triggered_by=triggered_by,
        )
        self._session.add(run)
        self._session.flush()
        return run

    def heartbeat(self, run: CollectionRun, at: datetime) -> None:
        """Actualiza la señal de vida de una ejecución activa."""
        run.heartbeat_at = at
        self._session.flush()

    def mark_abandoned(self, heartbeat_older_than: datetime) -> int:
        """Marca como error las filas ``running`` con heartbeat vencido.

        Ocurre cuando un proceso murió sin completar su registro. Devuelve
        cuántas filas se marcaron.
        """
        stale_runs = list(
            self._session.scalars(
                select(CollectionRun).where(
                    CollectionRun.status == CollectionRunStatus.RUNNING,
                    CollectionRun.heartbeat_at < heartbeat_older_than,
                )
            )
        )
        for run in stale_runs:
            run.status = CollectionRunStatus.ERROR
            run.finished_at = run.heartbeat_at
            run.duration_ms = (
                self._duration_ms(run.started_at, run.heartbeat_at)
                if run.heartbeat_at is not None
                else None
            )
            run.errors = ["abandonada: heartbeat vencido (proceso interrumpido)"]
        self._session.flush()
        return len(stale_runs)

    def finish_success(
        self, run: CollectionRun, result: CollectionResult, finished_at: datetime
    ) -> None:
        """Completa la ejecución con el resumen de la recolección."""
        run.heartbeat_at = finished_at
        run.finished_at = finished_at
        run.duration_ms = self._duration_ms(run.started_at, finished_at)
        run.status = CollectionRunStatus.SUCCESS
        run.servers_synced = result.servers_synced
        run.channels_synced = result.channels_synced
        run.server_metrics_inserted = result.server_metrics_inserted
        run.server_metrics_skipped = result.server_metrics_skipped
        run.channel_metrics_inserted = result.channel_metrics_inserted
        run.channel_metrics_skipped = result.channel_metrics_skipped
        run.channels_created = result.channels_created
        run.channels_updated = result.channels_updated
        run.channels_reactivated = result.channels_reactivated
        run.channels_deactivated = result.channels_deactivated
        run.channels_archived = result.channels_archived
        run.channels_unchanged = result.channels_unchanged
        run.channels_failed = result.channels_failed
        run.errors = list(result.errors)
        self._session.flush()

    def finish_error(self, run: CollectionRun, error: str, finished_at: datetime) -> None:
        """Marca la ejecución como fallida con el motivo."""
        run.heartbeat_at = finished_at
        run.finished_at = finished_at
        run.duration_ms = self._duration_ms(run.started_at, finished_at)
        run.status = CollectionRunStatus.ERROR
        run.errors = [error]
        self._session.flush()

    def latest(self) -> CollectionRun | None:
        """Última ejecución registrada, en cualquier estado."""
        stmt = (
            select(CollectionRun)
            .order_by(CollectionRun.started_at.desc(), CollectionRun.id.desc())
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    def latest_finished(self) -> CollectionRun | None:
        """Última ejecución terminada (success o error)."""
        stmt = (
            select(CollectionRun)
            .where(CollectionRun.status != CollectionRunStatus.RUNNING)
            .order_by(CollectionRun.started_at.desc(), CollectionRun.id.desc())
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    @staticmethod
    def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
        """Duración en milisegundos tolerante a naive/aware (SQLite)."""
        delta = ensure_utc(finished_at) - ensure_utc(started_at)
        return max(0, round(delta.total_seconds() * 1000))
