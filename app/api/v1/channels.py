"""Endpoints de consulta de canales y su histórico de métricas."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, to_utc
from app.api.pagination import NEXT_CURSOR_HEADER, decode_cursor, encode_cursor
from app.models.channel import Channel, ChannelEvent, ChannelMetric, ChannelType, TechnicalStream
from app.models.server import Server
from app.repositories.channel_repository import ChannelRepository
from app.schemas.channel import ChannelListItem, ChannelMetricRead, ChannelPage, ChannelRead

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=ChannelPage)
def list_channels(
    session: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort_by: Annotated[
        Literal[
            "name",
            "category",
            "server",
            "viewers",
            "bitrate",
            "output",
            "status",
            "last_updated_at",
        ],
        Query(),
    ] = "name",
    sort_order: Annotated[Literal["asc", "desc"], Query()] = "asc",
    server_id: Annotated[int | None, Query(description="Filtra por servidor actual")] = None,
    category: Annotated[
        str | None, Query(max_length=100, description="Filtra por categoría")
    ] = None,
    category_id: Annotated[
        str | None, Query(max_length=100, description="Filtra por identificador de categoría")
    ] = None,
    source_id: Annotated[str | None, Query(max_length=120, description="Filtra por fuente")] = None,
    channel_type: Annotated[
        ChannelType | None, Query(description="Filtra por tipo de canal")
    ] = None,
    active: Annotated[bool | None, Query(description="Filtra por actividad actual")] = None,
    event_start_from: Annotated[
        datetime | None, Query(description="Inicio de fecha del evento (ISO 8601)")
    ] = None,
    event_start_to: Annotated[
        datetime | None, Query(description="Fin de fecha del evento (ISO 8601)")
    ] = None,
    enabled: Annotated[bool | None, Query(description="Filtra por estado habilitado")] = None,
) -> ChannelPage:
    """Lista canales paginados con servidor y última métrica."""
    rows, total = ChannelRepository(session).list_page(
        page=page,
        page_size=page_size,
        search=search,
        server_id=server_id,
        category=category,
        category_id=category_id,
        source_id=source_id,
        channel_type=channel_type,
        active=active,
        event_start_from=to_utc(event_start_from),
        event_start_to=to_utc(event_start_to),
        enabled=enabled,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ChannelPage(
        items=[
            _channel_list_item(channel, server, metric, event, stream)
            for channel, server, metric, event, stream in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=(total + page_size - 1) // page_size,
    )


def _channel_list_item(
    channel: Channel,
    server: Server | None,
    metric: ChannelMetric | None,
    event: ChannelEvent | None,
    stream: TechnicalStream | None,
) -> ChannelListItem:
    latest_metric = ChannelMetricRead.model_validate(metric) if metric is not None else None
    return ChannelListItem(
        **ChannelRead.model_validate(channel).model_dump(),
        current_server_name=server.name if server is not None else None,
        event_external_id=event.external_id if event is not None else None,
        event_name=event.name if event is not None else None,
        technical_stream_external_id=stream.external_id if stream is not None else None,
        technical_stream_name=stream.name if stream is not None else None,
        latest_metric=latest_metric,
        viewers=metric.viewers if metric is not None else None,
        bitrate_mbps=metric.bitrate_mbps if metric is not None else None,
        estimated_output_mbps=metric.estimated_output_mbps if metric is not None else None,
        status=metric.status if metric is not None else None,
        last_updated_at=metric.collected_at if metric is not None else channel.updated_at,
    )


@router.get("/{channel_id}/metrics", response_model=list[ChannelMetricRead])
def list_channel_metrics(
    channel_id: int,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    start: Annotated[datetime | None, Query(description="Inicio del rango (ISO 8601)")] = None,
    end: Annotated[datetime | None, Query(description="Fin del rango (ISO 8601)")] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Máximo de muestras")] = 100,
    cursor: Annotated[str | None, Query(description="Cursor opaco de la página previa")] = None,
) -> list[ChannelMetricRead]:
    """Histórico de un canal, de más reciente a más antigua.

    Paginación por cursor: si hay más resultados, la cabecera
    ``X-Next-Cursor`` trae el cursor de la página siguiente. El cuerpo
    sigue siendo una lista, compatible con clientes que solo usan
    ``limit``.
    """
    repository = ChannelRepository(session)
    if repository.get(channel_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Canal no encontrado")
    metrics = repository.list_metrics(
        channel_id,
        start=to_utc(start),
        end=to_utc(end),
        limit=limit + 1,
        before=decode_cursor(cursor) if cursor is not None else None,
    )
    if len(metrics) > limit:
        metrics = metrics[:limit]
        response.headers[NEXT_CURSOR_HEADER] = encode_cursor(
            metrics[-1].collected_at, metrics[-1].id
        )
    return [ChannelMetricRead.model_validate(metric) for metric in metrics]
