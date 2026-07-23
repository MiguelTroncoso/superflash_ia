"""Acceso a datos de servidores y sus métricas."""

from datetime import datetime

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from app.adapters.base import ServerSnapshot
from app.models.server import Server, ServerMetric


class ServerRepository:
    """Consultas y persistencia sobre ``Server`` y ``ServerMetric``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[Server]:
        """Devuelve todos los servidores ordenados por nombre."""
        stmt = select(Server).order_by(Server.name)
        return list(self._session.scalars(stmt))

    def get(self, server_id: int) -> Server | None:
        """Busca un servidor por su id interno."""
        return self._session.get(Server, server_id)

    def get_by_external_id(self, external_id: str) -> Server | None:
        """Busca un servidor por su identificador externo."""
        stmt = select(Server).where(Server.external_id == external_id)
        return self._session.scalars(stmt).first()

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
