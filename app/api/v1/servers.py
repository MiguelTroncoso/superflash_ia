"""Endpoints de consulta de servidores y su histórico de métricas."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.prometheus import DatabasePrometheusInfrastructureAdapter
from app.api.deps import get_db, to_utc
from app.api.pagination import NEXT_CURSOR_HEADER, decode_cursor, encode_cursor
from app.core.config import Settings, get_settings
from app.models.server import Server, ServerMetric, ServerOperationalStatus
from app.repositories.server_repository import ServerRepository
from app.schemas.server import (
    ServerCreate,
    ServerDiagnosticCheck,
    ServerDiagnosticRead,
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


@router.get("/{server_id}", response_model=ServerRead)
def get_server(server_id: int, session: Annotated[Session, Depends(get_db)]) -> ServerRead:
    """Devuelve un servidor por su id interno."""
    server = ServerRepository(session).get(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor no encontrado")
    return _server_response(server)


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


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_server(server_id: int, session: Annotated[Session, Depends(get_db)]) -> Response:
    """Elimina un servidor del inventario y su histórico asociado."""
    repository = ServerRepository(session)
    server = repository.get(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor no encontrado")
    repository.delete(server)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.get("/{server_id}/diagnose", response_model=ServerDiagnosticRead)
def diagnose_server(
    server_id: int,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ServerDiagnosticRead:
    """Prueba Prometheus y Node Exporter sin ejecutar acciones externas."""
    repository = ServerRepository(session)
    server = repository.get(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor no encontrado")

    latest = repository.latest_metric(server.id)
    if not server.prometheus_url or not server.hostname:
        return ServerDiagnosticRead(
            server_id=server.id,
            server_name=server.name,
            status="not_configured",
            prometheus=ServerDiagnosticCheck(
                status="not_configured",
                message="Prometheus is not configured for this server",
            ),
            node_exporter=ServerDiagnosticCheck(
                status="not_configured",
                message="Node Exporter target is not configured",
            ),
            last_sample_at=latest.collected_at if latest is not None else None,
            errors=["Configure hostname and Prometheus URL to test the real source"],
        )

    probe = DatabasePrometheusInfrastructureAdapter(
        [server],
        timeout_seconds=settings.prometheus_timeout_seconds,
        verify_tls=settings.prometheus_tls_verify,
    ).probe_server(server)
    if not probe.reachable:
        error = _safe_probe_error(probe.error)
        return ServerDiagnosticRead(
            server_id=server.id,
            server_name=server.name,
            status="error",
            prometheus=ServerDiagnosticCheck(status="error", message="Prometheus query failed"),
            node_exporter=ServerDiagnosticCheck(
                status="error", message="Node Exporter could not be verified"
            ),
            last_sample_at=latest.collected_at if latest is not None else None,
            latency_ms=probe.latency_ms,
            errors=[error],
        )

    if probe.up_value == 1:
        exporter = ServerDiagnosticCheck(status="ok", message="Node Exporter OK")
        overall = "ok"
        errors: list[str] = []
    elif probe.up_value == 0:
        exporter = ServerDiagnosticCheck(
            status="error",
            message="Node Exporter reports down; verify service and firewall",
        )
        overall = "error"
        errors = ["Prometheus is reachable but Node Exporter reports up=0"]
    else:
        exporter = ServerDiagnosticCheck(
            status="no_data", message="Node Exporter returned no up sample"
        )
        overall = "no_data"
        errors = ["Prometheus is reachable but no Node Exporter sample is available"]

    return ServerDiagnosticRead(
        server_id=server.id,
        server_name=server.name,
        status=overall,
        prometheus=ServerDiagnosticCheck(status="ok", message="Prometheus OK"),
        node_exporter=exporter,
        last_sample_at=latest.collected_at if latest is not None else None,
        latency_ms=probe.latency_ms,
        errors=errors,
    )


def _safe_probe_error(error: str | None) -> str:
    """Traduce fallos de red/autenticación sin exponer URL ni credenciales."""
    if error == "configuracion_incompleta":
        return "Prometheus configuration is incomplete"
    if error and "credenciales" in error:
        return "Prometheus authentication failed"
    return "Prometheus is unreachable or returned an invalid response"
