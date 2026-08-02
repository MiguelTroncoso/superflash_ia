"""Endpoints internos de recolección: ejecución manual y estado.

Como todo ``/api/v1``, requieren la cabecera ``X-API-Key`` (política
fail-closed). El estado se lee del historial persistido en
``collection_runs`` con heartbeat: una ejecución solo se considera en
curso mientras su señal de vida no supere ``COLLECTION_TIMEOUT_SECONDS``.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters.factory import get_adapter
from app.api.deps import get_db
from app.collectors.runner import CollectionAlreadyRunningError, get_collection_runner
from app.core.config import Settings, get_settings
from app.core.timeutils import ensure_utc
from app.models.collection_run import CollectionRun, CollectionRunStatus, CollectionTrigger
from app.repositories.collection_run_repository import CollectionRunRepository
from app.schemas.collection import CollectionResult, CollectionStatusRead
from app.tasks.scheduler import get_active_scheduler

router = APIRouter(prefix="/collection", tags=["collection (interno)"])


@router.post("/run", response_model=CollectionResult)
def run_collection(
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CollectionResult:
    """Ejecuta una recolección con el adaptador configurado.

    Operación de solo lectura hacia la fuente externa; únicamente
    escribe en la base de datos propia de la plataforma. Si ya hay una
    recolección en curso (en este proceso o en otra instancia, vía
    advisory lock) responde 409 sin iniciar otra.
    """
    adapter = get_adapter(settings, session)
    try:
        return get_collection_runner().run(
            session,
            adapter,
            triggered_by=CollectionTrigger.MANUAL,
            timeout_seconds=settings.collection_timeout_seconds,
        )
    except CollectionAlreadyRunningError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya hay una recolección en curso",
        ) from None


def _status_from_run(
    run: CollectionRun, running: bool, next_run_at: datetime | None
) -> CollectionStatusRead:
    """Proyecta una fila de ``collection_runs`` al contrato estable."""
    return CollectionStatusRead(
        running=running,
        run_id=run.id,
        source=run.source,
        triggered_by=run.triggered_by,
        started_at=run.started_at,
        heartbeat_at=run.heartbeat_at,
        finished_at=run.finished_at,
        duration_ms=run.duration_ms,
        status=run.status,
        inserted=run.server_metrics_inserted + run.channel_metrics_inserted,
        skipped=run.server_metrics_skipped + run.channel_metrics_skipped,
        errors=list(run.errors),
        next_run_at=next_run_at,
    )


@router.get("/status", response_model=CollectionStatusRead)
def collection_status(
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CollectionStatusRead:
    """Estado del recolector según el historial persistido.

    Si hay una ejecución en curso (heartbeat vigente), la describe; si
    no, describe la última terminada. Sin historial devuelve el estado
    vacío con ``running=false``.
    """
    runner = get_collection_runner()
    scheduler = get_active_scheduler()
    next_run_at = scheduler.next_run_at if scheduler is not None else None
    runs = CollectionRunRepository(session)

    latest = runs.latest()
    if latest is not None and latest.status is CollectionRunStatus.RUNNING:
        heartbeat = ensure_utc(latest.heartbeat_at or latest.started_at)
        fresh = datetime.now(UTC) - heartbeat <= timedelta(
            seconds=settings.collection_timeout_seconds
        )
        if fresh or runner.is_running:
            return _status_from_run(latest, running=True, next_run_at=next_run_at)

    last_finished = runs.latest_finished()
    if last_finished is not None:
        return _status_from_run(last_finished, running=False, next_run_at=next_run_at)

    return CollectionStatusRead(running=False, next_run_at=next_run_at)
