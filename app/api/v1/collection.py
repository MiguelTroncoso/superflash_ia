"""Endpoints internos de recolección: ejecución manual y estado.

Como todo ``/api/v1``, requieren la cabecera ``X-API-Key`` (política
fail-closed). El estado se lee del historial persistido en
``collection_runs``, por lo que refleja recolecciones de cualquier
instancia y sobrevive a reinicios del proceso.
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
from app.models.collection_run import CollectionRunStatus, CollectionTrigger
from app.repositories.collection_run_repository import CollectionRunRepository
from app.schemas.collection import (
    CollectionResult,
    CollectionRunRead,
    CollectionStatusRead,
    SchedulerStatus,
)
from app.tasks.scheduler import get_active_scheduler

router = APIRouter(prefix="/collection", tags=["collection (interno)"])

# Una fila "running" más antigua que esto se considera huérfana (proceso
# caído sin completar el registro) y no se reporta como en ejecución.
STALE_RUNNING_AFTER = timedelta(minutes=30)


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
    adapter = get_adapter(settings)
    try:
        return get_collection_runner().run(session, adapter, triggered_by=CollectionTrigger.MANUAL)
    except CollectionAlreadyRunningError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya hay una recolección en curso",
        ) from None


@router.get("/status", response_model=CollectionStatusRead)
def collection_status(
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CollectionStatusRead:
    """Estado del recolector: última ejecución persistida, curso y scheduler."""
    runner = get_collection_runner()
    scheduler = get_active_scheduler()
    runs = CollectionRunRepository(session)

    running = runner.is_running
    current_started_at = runner.running_since
    latest = runs.latest()
    if not running and latest is not None and latest.status is CollectionRunStatus.RUNNING:
        started_at = ensure_utc(latest.started_at)
        if datetime.now(UTC) - started_at <= STALE_RUNNING_AFTER:
            # Recolección en curso en otra instancia (fila running fresca).
            running = True
            current_started_at = started_at

    last_finished = runs.latest_finished()
    return CollectionStatusRead(
        running=running,
        current_run_started_at=current_started_at,
        last_run=(
            CollectionRunRead.model_validate(last_finished) if last_finished is not None else None
        ),
        scheduler=SchedulerStatus(
            enabled=scheduler is not None and scheduler.is_active,
            interval_seconds=(
                scheduler.interval_seconds if scheduler else settings.collection_interval_seconds
            ),
            next_run_at=scheduler.next_run_at if scheduler else None,
        ),
    )
