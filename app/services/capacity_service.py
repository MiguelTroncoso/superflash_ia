"""Cálculos deterministas de capacidad, sin efectos secundarios."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.server import Server, ServerMetric
from app.repositories.server_repository import ServerRepository
from app.schemas.capacity import (
    CapacityDataQuality,
    CapacityOverviewRead,
    CapacityServerRead,
    CapacityState,
)


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _percent(load: float | None, capacity: float | None) -> float | None:
    if load is None or capacity is None or capacity <= 0:
        return None
    return _round(load / capacity * 100)


def _limits(server: Server) -> tuple[float | None, float | None, float | None, float]:
    physical = server.network_capacity_mbps
    operational = server.operational_network_limit_mbps or physical
    recommended = server.recommended_network_limit_mbps or operational
    reserve = server.minimum_network_reserve_mbps or 0.0
    return physical, operational, recommended, reserve


def capacity_state(
    metric: ServerMetric | None,
    physical: float | None,
    operational: float | None,
    recommended: float | None,
    reserve: float,
) -> CapacityState:
    """Clasifica una muestra usando exclusivamente límites configurados."""
    if metric is None or physical is None or operational is None or recommended is None:
        return CapacityState.NO_DATA
    load = max(metric.output_mbps, 0.0)
    target = max(operational - reserve, 0.0)
    if load > recommended or load > physical:
        return CapacityState.CRITICAL
    if load > operational:
        return CapacityState.HIGH
    if target > 0 and load > target * 0.8:
        return CapacityState.WARNING
    return CapacityState.NORMAL


def _server_read(server: Server, metric: ServerMetric | None) -> CapacityServerRead:
    physical, operational, recommended, reserve = _limits(server)
    load = max(metric.output_mbps, 0.0) if metric is not None else None
    has_configuration = physical is not None and operational is not None and recommended is not None
    physical_free = max(physical - load, 0.0) if physical is not None and load is not None else None
    operational_free = (
        max(operational - load, 0.0) if operational is not None and load is not None else None
    )
    return CapacityServerRead(
        server_id=server.id,
        name=server.name,
        provider=server.provider,
        group=server.group,
        physical_capacity_mbps=_round(physical),
        operational_limit_mbps=_round(operational),
        recommended_limit_mbps=_round(recommended),
        minimum_reserve_mbps=_round(reserve),
        observed_load_mbps=_round(load),
        physical_utilization_percent=_percent(load, physical),
        operational_utilization_percent=_percent(load, operational),
        physical_free_mbps=_round(physical_free),
        operational_free_mbps=_round(operational_free),
        safety_margin_mbps=_round(
            operational_free - reserve if operational_free is not None else None
        ),
        state=capacity_state(metric, physical, operational, recommended, reserve),
        data_quality=CapacityDataQuality.OBSERVED
        if metric is not None and has_configuration
        else CapacityDataQuality.INSUFFICIENT_DATA,
        last_collected_at=metric.collected_at if metric is not None else None,
    )


class CapacityService:
    """Construye la vista actual de capacidad con una consulta agregada."""

    def __init__(self, session: Session) -> None:
        self._servers = ServerRepository(session)

    def list_servers(self) -> list[CapacityServerRead]:
        return [
            _server_read(server, metric)
            for server, metric, _ in self._servers.latest_enabled_with_cost()
        ]

    def build(self) -> CapacityOverviewRead:
        rows = self._servers.latest_enabled_with_cost()
        servers = [_server_read(server, metric) for server, metric, _ in rows]
        configured = [server for server, _, _ in rows if server.network_capacity_mbps is not None]
        sampled = [metric for _, metric, _ in rows if metric is not None]
        missing_data = [
            server.name
            for server, metric, _ in rows
            if metric is None or server.network_capacity_mbps is None
        ]
        physical_total = sum(row.physical_capacity_mbps or 0 for row in servers)
        operational_total = sum(row.operational_limit_mbps or 0 for row in servers)
        observed_total = sum(row.observed_load_mbps or 0 for row in servers)
        physical_free = sum(row.physical_free_mbps or 0 for row in servers)
        operational_free = sum(row.operational_free_mbps or 0 for row in servers)
        quality = (
            CapacityDataQuality.OBSERVED
            if rows and not missing_data
            else CapacityDataQuality.INSUFFICIENT_DATA
        )
        return CapacityOverviewRead(
            generated_at=datetime.now(UTC),
            server_count=len(rows),
            configured_server_count=len(configured),
            sampled_server_count=len(sampled),
            total_physical_capacity_mbps=round(physical_total, 2),
            total_operational_limit_mbps=round(operational_total, 2),
            total_observed_load_mbps=round(observed_total, 2),
            total_physical_free_mbps=round(physical_free, 2),
            total_operational_free_mbps=round(operational_free, 2),
            data_quality=quality,
            missing_data=missing_data,
            servers=servers,
        )
