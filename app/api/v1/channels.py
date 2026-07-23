"""Endpoints de consulta de canales y su histórico de métricas."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, to_utc
from app.repositories.channel_repository import ChannelRepository
from app.schemas.channel import ChannelMetricRead, ChannelRead

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=list[ChannelRead])
def list_channels(
    session: Annotated[Session, Depends(get_db)],
    server_id: Annotated[int | None, Query(description="Filtra por servidor actual")] = None,
    category: Annotated[str | None, Query(description="Filtra por categoría")] = None,
    enabled: Annotated[bool | None, Query(description="Filtra por estado habilitado")] = None,
) -> list[ChannelRead]:
    """Lista canales con filtros opcionales."""
    channels = ChannelRepository(session).list_filtered(
        server_id=server_id, category=category, enabled=enabled
    )
    return [ChannelRead.model_validate(channel) for channel in channels]


@router.get("/{channel_id}/metrics", response_model=list[ChannelMetricRead])
def list_channel_metrics(
    channel_id: int,
    session: Annotated[Session, Depends(get_db)],
    start: Annotated[datetime | None, Query(description="Inicio del rango (ISO 8601)")] = None,
    end: Annotated[datetime | None, Query(description="Fin del rango (ISO 8601)")] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Máximo de muestras")] = 100,
) -> list[ChannelMetricRead]:
    """Histórico de métricas de un canal, de más reciente a más antigua."""
    repository = ChannelRepository(session)
    if repository.get(channel_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Canal no encontrado")
    metrics = repository.list_metrics(channel_id, start=to_utc(start), end=to_utc(end), limit=limit)
    return [ChannelMetricRead.model_validate(metric) for metric in metrics]
