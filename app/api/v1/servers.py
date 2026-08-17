"""Endpoints de consulta de servidores y su histórico de métricas."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, to_utc
from app.api.pagination import NEXT_CURSOR_HEADER, decode_cursor, encode_cursor
from app.models.server import Server, ServerMetric, ServerOperationalStatus
from app.repositories.server_repository import ServerRepository
from app.schemas.server import (
    ServerCreate,
    ServerDeletionImpact,
    ServerDeletionRequest,
    ServerDeletionResponse,
    ServerListItem,
    ServerMetricRead,
    ServerPage,
    ServerRead,
    ServerUpdate,
)
from app.services.overview_service import compute_network_utilization

router = APIRouter(prefix="/servers", tags=["servers"])


def _inventory_fields(payload: ServerCreate | ServerUpdate) -> dict[str, object]:
    """Traduce el contrato HTTP a los nombres del modelo ORM."""
    fields = payload.model_dump(exclude_unset=isinstance(payload, ServerUpdate))
    if "type" in fields:
        fields["server_type"] = fields.pop("type")
    if "network_speed_mbps" in fields:
        fields["network_capacity_mbps"] = fields.pop("network_speed_mbps")
    return fields


def _server_response(server: Server) -> ServerRead:
    """Construye la respuesta sin devolver el token de Prometheus."""
    return ServerRead.model_validate(server)


@router.post("", response_model=ServerRead, status_code=status.HTTP_201_CREATED)
def create_server(
    payload: ServerCreate,
    session: Annotated[Session, Depends(get_db)],
) -> ServerRead:
    """Registra un servidor en el inventario administrado."""
    repository = ServerRepository(session)
    if repository.get_by_external_id(payload.external_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="external_id ya existe")
    try:
        server = repository.create(_inventory_fields(payload))
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="external_id ya existe"
        ) from None
    return _server_response(server)


@router.get("", response_model=ServerPage)
def list_servers(
    session: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort_by: Annotated[
        Literal[
            "name",
            "status",
            "provider",
            "group",
            "country",
            "created_at",
            "updated_at",
            "cpu",
            "memory",
            "disk",
            "network",
            "uptime",
            "last_updated_at",
        ],
        Query(),
    ] = "name",
    sort_order: Annotated[Literal["asc", "desc"], Query()] = "asc",
    status_filter: Annotated[ServerOperationalStatus | None, Query(alias="status")] = None,
    provider: Annotated[str | None, Query(max_length=120)] = None,
    group: Annotated[str | None, Query(max_length=120)] = None,
    enabled: Annotated[bool | None, Query()] = None,
    lifecycle_state: Annotated[Literal["active", "archived", "all"], Query()] = "active",
) -> ServerPage:
    """Lista servidores paginados con sus agregados operativos."""
    rows, total = ServerRepository(session).list_page(
        page=page,
        page_size=page_size,
        search=search,
        status=status_filter,
        provider=provider,
        group=group,
        enabled=enabled,
        lifecycle_state=lifecycle_state,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ServerPage(
        items=[
            _server_list_item(server, metric, active_alert_count)
            for server, metric, active_alert_count in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=_total_pages(total, page_size),
    )


def _server_list_item(
    server: Server,
    metric: ServerMetric | None,
    active_alert_count: int,
) -> ServerListItem:
    latest_metric = ServerMetricRead.model_validate(metric) if metric is not None else None
    return ServerListItem(
        **ServerRead.model_validate(server).model_dump(),
        latest_metric=latest_metric,
        network_utilization_percent=(
            compute_network_utilization(metric.output_mbps, server.network_capacity_mbps)
            if metric is not None
            else None
        ),
        active_alert_count=active_alert_count,
        last_updated_at=metric.collected_at if metric is not None else server.updated_at,
    )


def _total_pages(total: int, page_size: int) -> int:
    return (total + page_size - 1) // page_size


def _operator_actor(value: str | None) -> str:
    clean = "".join(
        character
        for character in (value or "api-key-operator")
        if character.isalnum() or character in "._@-"
    )
    return clean[:120] or "api-key-operator"


@router.patch("/{server_id}", response_model=ServerRead)
@router.put("/{server_id}", response_model=ServerRead)
def update_server(
    server_id: int,
    payload: ServerUpdate,
    session: Annotated[Session, Depends(get_db)],
) -> ServerRead:
    """Actualiza un servidor existente sin exponer credenciales."""
    repository = ServerRepository(session)
    server = repository.get(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor no encontrado")
    if "external_id" in payload.model_fields_set:
        duplicate = repository.get_by_external_id(payload.external_id or "")
        if duplicate is not None and duplicate.id != server_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="external_id ya existe"
            )
    try:
        repository.update(server, _inventory_fields(payload))
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="external_id ya existe"
        ) from None
    return _server_response(server)


@router.get("/{server_id}/deletion-impact", response_model=ServerDeletionImpact)
def get_server_deletion_impact(
    server_id: int,
    session: Annotated[Session, Depends(get_db)],
) -> ServerDeletionImpact:
    """Muestra el impacto del retiro sin exponer datos sensibles."""
    repository = ServerRepository(session)
    server = repository.get(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor no encontrado")
    relations = repository.relation_summary(server)
    return ServerDeletionImpact(
        server_id=server.id,
        name=server.name,
        hostname=server.hostname,
        relations=relations,
        can_hard_delete=repository.can_hard_delete(relations),
    )


@router.get("/{server_id}", response_model=ServerRead)
def get_server(server_id: int, session: Annotated[Session, Depends(get_db)]) -> ServerRead:
    """Devuelve un servidor por su id interno."""
    server = ServerRepository(session).get(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor no encontrado")
    return _server_response(server)


@router.delete("/{server_id}", response_model=ServerDeletionResponse)
def delete_server(
    server_id: int,
    payload: ServerDeletionRequest,
    session: Annotated[Session, Depends(get_db)],
    operator_id: Annotated[str | None, Header(alias="X-Operator-Id")] = None,
) -> ServerDeletionResponse:
    """Retira un servidor con confirmación explícita y sin borrar histórico productivo.

    Un registro sin métricas, alertas, snapshots, canales, costes ni jobs no
    cancelados puede eliminarse por completo. En cualquier otro caso solo se
    archiva y conserva su histórico. No existe un purge público.
    """
    repository = ServerRepository(session)
    server = repository.get(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor no encontrado")
    if payload.confirmation != server.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La confirmación debe coincidir exactamente con el nombre del servidor",
        )
    if server.hostname is not None and payload.hostname != server.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La confirmación de host no coincide con el servidor",
        )

    relations = repository.relation_summary(server)
    cancelled_jobs = 0
    if server.lifecycle_state != "archived":
        cancelled_jobs = repository.cancel_active_onboardings(
            server.id,
            _operator_actor(operator_id),
        )
        relations = repository.relation_summary(server)

    # A running background worker needs the cancelled row to remain visible
    # until the operator performs a later explicit cleanup. This prevents a
    # concurrent worker from losing the cancellation marker after a cascade.
    if cancelled_jobs == 0 and repository.can_hard_delete(relations):
        name = server.name
        hostname = server.hostname
        repository.delete(server)
        session.commit()
        return ServerDeletionResponse(
            server_id=server_id,
            name=name,
            hostname=hostname,
            relations=relations,
            can_hard_delete=True,
            action="deleted",
            cancelled_onboarding_jobs=cancelled_jobs,
        )

    repository.archive(server)
    session.commit()
    return ServerDeletionResponse(
        server_id=server.id,
        name=server.name,
        hostname=server.hostname,
        relations=relations,
        can_hard_delete=False,
        action="archived",
        cancelled_onboarding_jobs=cancelled_jobs,
    )


@router.get("/{server_id}/metrics", response_model=list[ServerMetricRead])
def list_server_metrics(
    server_id: int,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    start: Annotated[datetime | None, Query(description="Inicio del rango (ISO 8601)")] = None,
    end: Annotated[datetime | None, Query(description="Fin del rango (ISO 8601)")] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Máximo de muestras")] = 100,
    cursor: Annotated[str | None, Query(description="Cursor opaco de la página previa")] = None,
) -> list[ServerMetricRead]:
    """Histórico de un servidor, de más reciente a más antigua.

    Paginación por cursor: si hay más resultados, la cabecera
    ``X-Next-Cursor`` trae el cursor de la página siguiente. El cuerpo
    sigue siendo una lista, compatible con clientes que solo usan
    ``limit``.
    """
    repository = ServerRepository(session)
    if repository.get(server_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor no encontrado")
    metrics = repository.list_metrics(
        server_id,
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
    return [ServerMetricRead.model_validate(metric) for metric in metrics]
