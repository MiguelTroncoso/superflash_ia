"""Endpoints internos de recolección: ejecución manual y estado.

``POST /run`` está protegido por API key (cabecera ``X-API-Key``,
configurada vía ``COLLECTION_API_KEY``) con política fail-closed: sin
clave configurada, el endpoint responde 503. ``GET /status`` es de solo
lectura y no expone información sensible, por lo que queda abierto como
el resto de los endpoints de consulta.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters.factory import get_adapter
from app.api.deps import get_db, require_collection_api_key
from app.collectors.runner import CollectionAlreadyRunningError, get_collection_runner
from app.core.config import Settings, get_settings
from app.schemas.collection import CollectionResult, CollectionStatusRead, SchedulerStatus
from app.tasks.scheduler import get_active_scheduler

router = APIRouter(prefix="/collection", tags=["collection (interno)"])


@router.post(
    "/run",
    response_model=CollectionResult,
    dependencies=[Depends(require_collection_api_key)],
)
def run_collection(
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CollectionResult:
    """Ejecuta una recolección con el adaptador configurado (mock).

    Operación de solo lectura hacia la fuente externa; únicamente
    escribe en la base de datos propia de la plataforma. Si ya hay una
    recolección en curso responde 409 sin iniciar otra.
    """
    adapter = get_adapter(settings)
    try:
        return get_collection_runner().run(session, adapter)
    except CollectionAlreadyRunningError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya hay una recolección en curso",
        ) from None


@router.get("/status", response_model=CollectionStatusRead)
def collection_status(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CollectionStatusRead:
    """Estado del recolector: última ejecución, ejecución en curso y scheduler."""
    runner = get_collection_runner()
    scheduler = get_active_scheduler()
    return CollectionStatusRead(
        running=runner.is_running,
        current_run_started_at=runner.running_since,
        last_run=runner.last_run,
        scheduler=SchedulerStatus(
            enabled=scheduler is not None and scheduler.is_active,
            interval_seconds=(
                scheduler.interval_seconds if scheduler else settings.collection_interval_seconds
            ),
            next_run_at=scheduler.next_run_at if scheduler else None,
        ),
    )
