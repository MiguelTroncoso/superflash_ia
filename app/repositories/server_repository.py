"""Acceso a datos de servidores y sus métricas."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import Select, and_, desc, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.alert import Alert, AlertStatus
from app.models.intelligence import ServerCostProfile
from app.models.server import Server, ServerMetric

if TYPE_CHECKING:
    from app.adapters.base import ServerSnapshot


class ServerRepository:
    """Consultas y persistencia sobre ``Server`` y ``ServerMetric``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[Server]:
        """Devuelve todos los servidores ordenados por nombre."""
        stmt = select(Server).order_by(Server.name)
        return list(self._session.scalars(stmt))

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        status: str | None = None,
        provider: str | None = None,
        group: str | None = None,
        enabled: bool | None = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> tuple[list[tuple[Server, ServerMetric | None, int]], int]:
        """Devuelve una página con última métrica y alertas activas agregadas.

        La consulta de datos usa subconsultas para seleccionar una sola muestra
        por servidor y un resumen agrupado de alertas. No consulta por fila.
        """
        filters = self._page_filters(
            search=search,
            status=status,
            provider=provider,
            group=group,
            enabled=enabled,
        )
        total = self._session.scalar(select(func.count(Server.id)).where(*filters)) or 0

        latest = (
            select(
                ServerMetric.server_id,
                func.max(ServerMetric.collected_at).label("max_collected_at"),
            )
            .group_by(ServerMetric.server_id)
            .subquery()
        )
        active_alerts = (
            select(
                Alert.server_id,
                func.count(Alert.id).label("active_alert_count"),
            )
            .where(Alert.status != AlertStatus.RESOLVED)
            .group_by(Alert.server_id)
            .subquery()
        )
        metric_join = and_(
            ServerMetric.server_id == Server.id,
            ServerMetric.server_id == latest.c.server_id,
            ServerMetric.collected_at == latest.c.max_collected_at,
        )
        stmt = (
            select(
                Server,
                ServerMetric,
                func.coalesce(active_alerts.c.active_alert_count, 0),
            )
            .select_from(Server)
            .outerjoin(latest, latest.c.server_id == Server.id)
            .outerjoin(ServerMetric, metric_join)
            .outerjoin(active_alerts, active_alerts.c.server_id == Server.id)
            .where(*filters)
            .order_by(*self._sort_expressions(sort_by, sort_order))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = [(row[0], row[1], int(row[2])) for row in self._session.execute(stmt).all()]
        return rows, int(total)

    @staticmethod
    def _page_filters(
        *,
        search: str | None,
        status: str | None,
        provider: str | None,
        group: str | None,
        enabled: bool | None,
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = []
        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    Server.name.ilike(term),
                    Server.hostname.ilike(term),
                    Server.external_id.ilike(term),
                    Server.country.ilike(term),
                )
            )
        if status is not None:
            filters.append(Server.status == status)
        if provider is not None:
            filters.append(Server.provider == provider)
        if group is not None:
            filters.append(Server.group == group)
        if enabled is not None:
            filters.append(Server.enabled.is_(enabled))
        return filters

    @staticmethod
    def _sort_expressions(sort_by: str, sort_order: str) -> tuple[ColumnElement[Any], ...]:
        fields: dict[str, Any] = {
            "name": Server.name,
            "status": Server.status,
            "provider": Server.provider,
            "group": Server.group,
            "country": Server.country,
            "created_at": Server.created_at,
            "updated_at": Server.updated_at,
            "cpu": ServerMetric.cpu_percent,
            "memory": ServerMetric.memory_percent,
            "disk": ServerMetric.disk_percent,
            "network": ServerMetric.output_mbps,
            "uptime": ServerMetric.uptime_seconds,
            "last_updated_at": ServerMetric.collected_at,
        }
        expression = cast(ColumnElement[Any], fields[sort_by])
        ordered = (
            expression.desc().nulls_last()
            if sort_order == "desc"
            else expression.asc().nulls_last()
        )
        return ordered, Server.id.asc()

    def list_enabled_with_prometheus(self) -> list[Server]:
        """Devuelve targets habilitados con URL Prometheus configurada."""
        stmt = (
            select(Server)
            .where(Server.enabled.is_(True), Server.prometheus_url.is_not(None))
            .order_by(Server.name)
        )
        return list(self._session.scalars(stmt))

    def get(self, server_id: int) -> Server | None:
        """Busca un servidor por su id interno."""
        return self._session.get(Server, server_id)

    def get_by_external_id(self, external_id: str) -> Server | None:
        """Busca un servidor por su identificador externo."""
        stmt = select(Server).where(Server.external_id == external_id)
        return self._session.scalars(stmt).first()

    def create(self, fields: dict[str, object]) -> Server:
        """Crea un servidor administrado desde el inventario."""
        server = Server(**fields)
        self._session.add(server)
        self._session.flush()
        return server

    def update(self, server: Server, fields: dict[str, object]) -> Server:
        """Actualiza únicamente los campos enviados por el cliente."""
        for name, value in fields.items():
            setattr(server, name, value)
        self._session.flush()
        return server

    def delete(self, server: Server) -> None:
        """Elimina un servidor y sus métricas por la relación configurada."""
        self._session.delete(server)
        self._session.flush()

    def upsert_from_snapshot(self, snapshot: ServerSnapshot) -> Server:
        """Crea o actualiza un servidor identificado por ``external_id``."""
        server = self.get_by_external_id(snapshot.external_id)
        if server is None:
            server = Server(external_id=snapshot.external_id)
            self._session.add(server)
        server.name = snapshot.name
        server.hostname = snapshot.hostname
        server.role = snapshot.role
        server.network_capacity_mbps = snapshot.network_capacity_mbps
        server.enabled = snapshot.enabled
        self._session.flush()
        return server

    def metric_exists(self, server_id: int, collected_at: datetime) -> bool:
        """Indica si ya existe una muestra para ese servidor y ese instante."""
        stmt = select(ServerMetric.id).where(
            ServerMetric.server_id == server_id,
            ServerMetric.collected_at == collected_at,
        )
        return self._session.scalars(stmt).first() is not None

    def add_metric(self, metric: ServerMetric) -> None:
        """Registra una nueva muestra de métricas."""
        self._session.add(metric)
        self._session.flush()

    def list_metrics(
        self,
        server_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
        before: tuple[datetime, int] | None = None,
    ) -> list[ServerMetric]:
        """Histórico de un servidor, de más reciente a más antigua.

        ``before`` es la posición ``(collected_at, id)`` del cursor: solo
        se devuelven muestras estrictamente anteriores en el orden
        estable ``(collected_at DESC, id DESC)``.
        """
        stmt: Select[tuple[ServerMetric]] = select(ServerMetric).where(
            ServerMetric.server_id == server_id
        )
        if start is not None:
            stmt = stmt.where(ServerMetric.collected_at >= start)
        if end is not None:
            stmt = stmt.where(ServerMetric.collected_at <= end)
        if before is not None:
            before_at, before_id = before
            stmt = stmt.where(
                or_(
                    ServerMetric.collected_at < before_at,
                    and_(ServerMetric.collected_at == before_at, ServerMetric.id < before_id),
                )
            )
        stmt = stmt.order_by(ServerMetric.collected_at.desc(), ServerMetric.id.desc()).limit(limit)
        return list(self._session.scalars(stmt))

    def latest_metrics_for_enabled(self) -> list[tuple[Server, ServerMetric]]:
        """Última muestra disponible de cada servidor habilitado."""
        latest = (
            select(
                ServerMetric.server_id,
                func.max(ServerMetric.collected_at).label("max_collected_at"),
            )
            .group_by(ServerMetric.server_id)
            .subquery()
        )
        stmt = (
            select(Server, ServerMetric)
            .join(ServerMetric, ServerMetric.server_id == Server.id)
            .join(
                latest,
                (ServerMetric.server_id == latest.c.server_id)
                & (ServerMetric.collected_at == latest.c.max_collected_at),
            )
            .where(Server.enabled.is_(True))
            .order_by(Server.name)
        )
        return [(row[0], row[1]) for row in self._session.execute(stmt).all()]

    def latest_enabled_with_cost(
        self,
    ) -> list[tuple[Server, ServerMetric | None, ServerCostProfile | None]]:
        """Devuelve inventario habilitado, última métrica y coste en una consulta.

        La unión externa conserva servidores sin datos o sin perfil financiero,
        necesarios para mostrar ``no_data`` y ``insufficient_data`` sin hacer
        consultas adicionales por servidor.
        """
        latest = (
            select(
                ServerMetric.server_id,
                func.max(ServerMetric.collected_at).label("max_collected_at"),
            )
            .group_by(ServerMetric.server_id)
            .subquery()
        )
        metric_join = and_(
            ServerMetric.server_id == Server.id,
            ServerMetric.server_id == latest.c.server_id,
            ServerMetric.collected_at == latest.c.max_collected_at,
        )
        stmt = (
            select(Server, ServerMetric, ServerCostProfile)
            .select_from(Server)
            .outerjoin(latest, latest.c.server_id == Server.id)
            .outerjoin(ServerMetric, metric_join)
            .outerjoin(ServerCostProfile, ServerCostProfile.server_id == Server.id)
            .where(Server.enabled.is_(True))
            .order_by(Server.name, Server.id)
        )
        return [(row[0], row[1], row[2]) for row in self._session.execute(stmt).all()]

    def count_enabled(self) -> int:
        """Número de servidores habilitados."""
        stmt = select(func.count()).select_from(Server).where(Server.enabled.is_(True))
        return self._session.scalars(stmt).one()

    def recent_history(
        self, limit: int = 24
    ) -> list[tuple[datetime, float | None, float | None, float | None, float, float]]:
        """Agrega una ventana histórica común sin cargar métricas por servidor."""
        recent_timestamps = (
            select(ServerMetric.collected_at)
            .join(Server, ServerMetric.server_id == Server.id)
            .where(Server.enabled.is_(True))
            .distinct()
            .order_by(desc(ServerMetric.collected_at))
            .limit(limit)
            .subquery()
        )
        stmt = (
            select(
                ServerMetric.collected_at,
                func.avg(ServerMetric.cpu_percent),
                func.avg(ServerMetric.memory_percent),
                func.avg(ServerMetric.disk_percent),
                func.sum(ServerMetric.input_mbps),
                func.sum(ServerMetric.output_mbps),
            )
            .join(Server, ServerMetric.server_id == Server.id)
            .where(
                Server.enabled.is_(True),
                ServerMetric.collected_at.in_(select(recent_timestamps.c.collected_at)),
            )
            .group_by(ServerMetric.collected_at)
            .order_by(ServerMetric.collected_at.asc())
        )
        return [
            (
                row[0],
                float(row[1]) if row[1] is not None else None,
                float(row[2]) if row[2] is not None else None,
                float(row[3]) if row[3] is not None else None,
                float(row[4] or 0),
                float(row[5] or 0),
            )
            for row in self._session.execute(stmt).all()
        ]
