"""Endpoints de consulta de servidores y su histórico de métricas."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, to_utc
from app.repositories.server_repository import ServerRepository
from app.schemas.server import ServerMetricRead, ServerRead

router = APIRouter(prefix="/servers", tags=["servers"])


@router.get("", response_model=list[ServerRead])
def list_servers(session: Annotated[Session, Depends(get_db)]) -> list[ServerRead]:
    """Lista todos los servidores registrados."""
    servers = ServerRepository(session).list_all()
    return [ServerRead.model_validate(server) for server in servers]


@router.get("/{server_id}", response_model=ServerRead)
def get_server(server_id: int, session: Annotated[Session, Depends(get_db)]) -> ServerRead:
    """Devuelve un servidor por su id interno."""
    server = ServerRepository(session).get(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor no encontrado")
    return ServerRead.model_validate(server)


@router.get("/{server_id}/metrics", response_model=list[ServerMetricRead])
def list_server_metrics(
    server_id: int,
    session: Annotated[Session, Depends(get_db)],
    start: Annotated[datetime | None, Query(description="Inicio del rango (ISO 8601)")] = None,
    end: Annotated[datetime | None, Query(description="Fin del rango (ISO 8601)")] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Máximo de muestras")] = 100,
) -> list[ServerMetricRead]:
    """Histórico de métricas de un servidor, de más reciente a más antigua."""
    repository = ServerRepository(session)
    if repository.get(server_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor no encontrado")
    metrics = repository.list_metrics(server_id, start=to_utc(start), end=to_utc(end), limit=limit)
    return [ServerMetricRead.model_validate(metric) for metric in metrics]
