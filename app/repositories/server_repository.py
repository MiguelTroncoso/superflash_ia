"""Acceso a datos de servidores y sus métricas."""

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import Select, and_, desc, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.adapters.base import ServerSnapshot
from app.models.alert import Alert, AlertStatus
from app.models.channel import Channel, ChannelCategoryHistory, ChannelMetric
from app.models.onboarding import OnboardingAuditEvent, ServerInventorySnapshot, ServerOnboarding
from app.models.server import Server, ServerLifecycleState, ServerMetric

ACTIVE_ONBOARDING_STATUSES = (
    "pending",
    "connecting",
    "authenticating",
    "discovering",
    "installing_exporter",
    "configuring_firewall",
    "verifying_exporter",
    "registering_inventory",
    "configuring_monitoring",
    "validating",
)


class ServerRepository:
    """Consultas y persistencia sobre ``Server`` y ``ServerMetric``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[Server]:
        """Devuelve todos los servidores ordenados por nombre."""
        stmt = (
            select(Server)
            .where(Server.lifecycle_state == ServerLifecycleState.ACTIVE)
            .order_by(Server.name)
        )
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
        lifecycle_state: str = ServerLifecycleState.ACTIVE.value,
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
            lifecycle_state=lifecycle_state,
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
        lifecycle_state: str | None,
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
        if lifecycle_state != "all":
            filters.append(Server.lifecycle_state == lifecycle_state)
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

    def relation_summary(self, server: Server) -> dict[str, int]:
        """Cuenta relaciones antes de retirar un servidor.

        Las consultas son agregados constantes y no cargan históricos en
        memoria. Los dominios de simulación no existen en este esquema aún,
        por lo que se reportan explícitamente como cero.
        """

        def count(stmt: Any) -> int:
            return int(self._session.scalar(stmt) or 0)

        return {
            "metrics": count(
                select(func.count())
                .select_from(ServerMetric)
                .where(ServerMetric.server_id == server.id)
            ),
            "alerts": count(
                select(func.count()).select_from(Alert).where(Alert.server_id == server.id)
            ),
            "inventory_snapshots": count(
                select(func.count())
                .select_from(ServerInventorySnapshot)
                .where(ServerInventorySnapshot.server_id == server.id)
            ),
            "onboarding_jobs": count(
                select(func.count())
                .select_from(ServerOnboarding)
                .where(ServerOnboarding.server_id == server.id)
            ),
            "non_cancelled_onboarding_jobs": count(
                select(func.count())
                .select_from(ServerOnboarding)
                .where(
                    ServerOnboarding.server_id == server.id,
                    ServerOnboarding.status != "cancelled",
                )
            ),
            "onboarding_audit_events": count(
                select(func.count())
                .select_from(OnboardingAuditEvent)
                .where(OnboardingAuditEvent.server_id == server.id)
            ),
            "assigned_channels": count(
                select(func.count())
                .select_from(Channel)
                .where(Channel.current_server_id == server.id)
            ),
            "channel_metrics": count(
                select(func.count())
                .select_from(ChannelMetric)
                .where(ChannelMetric.server_id == server.id)
            ),
            "category_history": count(
                select(func.count())
                .select_from(ChannelCategoryHistory)
                .join(Channel, Channel.id == ChannelCategoryHistory.channel_id)
                .where(Channel.current_server_id == server.id)
            ),
            "cost_records": int(server.monthly_cost is not None),
            "simulation_records": 0,
        }

    @staticmethod
    def can_hard_delete(relations: dict[str, int]) -> bool:
        """Solo permite borrar registros sin histórico productivo."""

        protected = (
            "metrics",
            "alerts",
            "inventory_snapshots",
            "non_cancelled_onboarding_jobs",
            "assigned_channels",
            "channel_metrics",
            "category_history",
            "cost_records",
            "simulation_records",
        )
        return all(relations[name] == 0 for name in protected)

    def cancel_active_onboardings(self, server_id: int, actor: str) -> int:
        """Terminaliza jobs activos antes de retirar un servidor de prueba."""

        stmt = select(ServerOnboarding).where(
            ServerOnboarding.server_id == server_id,
            ServerOnboarding.status.in_(ACTIVE_ONBOARDING_STATUSES),
        )
        jobs = list(self._session.scalars(stmt))
        now = datetime.now(UTC)
        for onboarding in jobs:
            onboarding.status = "cancelled"
            onboarding.cancel_requested = True
            onboarding.last_error_code = "cancelled"
            onboarding.last_error_message_sanitized = "Onboarding cancelado por el operador."
            onboarding.updated_at = now
            self._session.add(
                OnboardingAuditEvent(
                    onboarding_id=onboarding.id,
                    server_id=server_id,
                    actor=actor,
                    event="cancelled_for_server_removal",
                    step=onboarding.current_step,
                    success=False,
                    detail_sanitized="Job de onboarding cancelado antes de retirar el servidor.",
                    created_at=now,
                )
            )
        self._session.flush()
        return len(jobs)

    def archive(self, server: Server) -> None:
        """Retira un servidor sin borrar sus datos históricos."""

        server.lifecycle_state = ServerLifecycleState.ARCHIVED
        server.archived_at = datetime.now(UTC)
        server.enabled = False
        self._session.flush()

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
