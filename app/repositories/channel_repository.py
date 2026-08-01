"""Acceso a datos de canales y sus métricas."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.adapters.base import ChannelSnapshot
from app.models.channel import Channel, ChannelMetric
from app.models.server import Server


class ChannelRepository:
    """Consultas y persistencia sobre ``Channel`` y ``ChannelMetric``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_filtered(
        self,
        server_id: int | None = None,
        category: str | None = None,
        enabled: bool | None = None,
    ) -> list[Channel]:
        """Lista canales aplicando filtros opcionales."""
        stmt: Select[tuple[Channel]] = select(Channel)
        if server_id is not None:
            stmt = stmt.where(Channel.current_server_id == server_id)
        if category is not None:
            stmt = stmt.where(Channel.category == category)
        if enabled is not None:
            stmt = stmt.where(Channel.enabled.is_(enabled))
        stmt = stmt.order_by(Channel.name)
        return list(self._session.scalars(stmt))

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        server_id: int | None = None,
        category: str | None = None,
        enabled: bool | None = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> tuple[list[tuple[Channel, Server | None, ChannelMetric | None]], int]:
        """Devuelve una página con servidor y última métrica por canal."""
        filters = self._page_filters(
            search=search,
            server_id=server_id,
            category=category,
            enabled=enabled,
        )
        count_stmt = (
            select(func.count(Channel.id))
            .select_from(Channel)
            .outerjoin(Server, Channel.current_server_id == Server.id)
            .where(*filters)
        )
        total = self._session.scalar(count_stmt) or 0

        latest = (
            select(
                ChannelMetric.channel_id,
                func.max(ChannelMetric.collected_at).label("max_collected_at"),
            )
            .group_by(ChannelMetric.channel_id)
            .subquery()
        )
        metric_join = and_(
            ChannelMetric.channel_id == Channel.id,
            ChannelMetric.channel_id == latest.c.channel_id,
            ChannelMetric.collected_at == latest.c.max_collected_at,
        )
        stmt = (
            select(Channel, Server, ChannelMetric)
            .select_from(Channel)
            .outerjoin(Server, Channel.current_server_id == Server.id)
            .outerjoin(latest, latest.c.channel_id == Channel.id)
            .outerjoin(ChannelMetric, metric_join)
            .where(*filters)
            .order_by(*self._sort_expressions(sort_by, sort_order))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = [(row[0], row[1], row[2]) for row in self._session.execute(stmt).all()]
        return rows, int(total)

    @staticmethod
    def _page_filters(
        *,
        search: str | None,
        server_id: int | None,
        category: str | None,
        enabled: bool | None,
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = []
        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    Channel.name.ilike(term),
                    Channel.external_id.ilike(term),
                    Channel.category.ilike(term),
                    Server.name.ilike(term),
                )
            )
        if server_id is not None:
            filters.append(Channel.current_server_id == server_id)
        if category is not None:
            filters.append(Channel.category == category)
        if enabled is not None:
            filters.append(Channel.enabled.is_(enabled))
        return filters

    @staticmethod
    def _sort_expressions(sort_by: str, sort_order: str) -> tuple[ColumnElement[Any], ...]:
        fields: dict[str, Any] = {
            "name": Channel.name,
            "category": Channel.category,
            "server": Server.name,
            "viewers": ChannelMetric.viewers,
            "bitrate": ChannelMetric.bitrate_mbps,
            "output": ChannelMetric.estimated_output_mbps,
            "status": ChannelMetric.status,
            "last_updated_at": ChannelMetric.collected_at,
        }
        expression = cast(ColumnElement[Any], fields[sort_by])
        ordered = (
            expression.desc().nulls_last()
            if sort_order == "desc"
            else expression.asc().nulls_last()
        )
        return ordered, Channel.id.asc()

    def get(self, channel_id: int) -> Channel | None:
        """Busca un canal por su id interno."""
        return self._session.get(Channel, channel_id)

    def get_by_external_id(self, external_id: str) -> Channel | None:
        """Busca un canal por su identificador externo."""
        stmt = select(Channel).where(Channel.external_id == external_id)
        return self._session.scalars(stmt).first()

    def count(self) -> int:
        """Cuenta los canales registrados."""
        return int(self._session.scalar(select(func.count(Channel.id))) or 0)

    def upsert_from_snapshot(
        self, snapshot: ChannelSnapshot, current_server_id: int | None
    ) -> Channel:
        """Crea o actualiza un canal identificado por ``external_id``."""
        channel = self.get_by_external_id(snapshot.external_id)
        if channel is None:
            channel = Channel(external_id=snapshot.external_id)
            self._session.add(channel)
        channel.name = snapshot.name
        channel.category = snapshot.category
        channel.current_server_id = current_server_id
        channel.enabled = snapshot.enabled
        self._session.flush()
        return channel

    def metric_exists(self, channel_id: int, collected_at: datetime) -> bool:
        """Indica si ya existe una muestra para ese canal y ese instante."""
        stmt = select(ChannelMetric.id).where(
            ChannelMetric.channel_id == channel_id,
            ChannelMetric.collected_at == collected_at,
        )
        return self._session.scalars(stmt).first() is not None

    def add_metric(self, metric: ChannelMetric) -> None:
        """Registra una nueva muestra de métricas."""
        self._session.add(metric)
        self._session.flush()

    def list_metrics(
        self,
        channel_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
        before: tuple[datetime, int] | None = None,
    ) -> list[ChannelMetric]:
        """Histórico de un canal, de más reciente a más antigua.

        ``before`` es la posición ``(collected_at, id)`` del cursor: solo
        se devuelven muestras estrictamente anteriores en el orden
        estable ``(collected_at DESC, id DESC)``.
        """
        stmt: Select[tuple[ChannelMetric]] = select(ChannelMetric).where(
            ChannelMetric.channel_id == channel_id
        )
        if start is not None:
            stmt = stmt.where(ChannelMetric.collected_at >= start)
        if end is not None:
            stmt = stmt.where(ChannelMetric.collected_at <= end)
        if before is not None:
            before_at, before_id = before
            stmt = stmt.where(
                or_(
                    ChannelMetric.collected_at < before_at,
                    and_(ChannelMetric.collected_at == before_at, ChannelMetric.id < before_id),
                )
            )
        stmt = stmt.order_by(ChannelMetric.collected_at.desc(), ChannelMetric.id.desc()).limit(
            limit
        )
        return list(self._session.scalars(stmt))

    def top_channels_by_latest_viewers(self, limit: int = 5) -> list[tuple[Channel, ChannelMetric]]:
        """Canales con más espectadores según la última muestra de cada uno."""
        latest = (
            select(
                ChannelMetric.channel_id,
                func.max(ChannelMetric.collected_at).label("max_collected_at"),
            )
            .group_by(ChannelMetric.channel_id)
            .subquery()
        )
        stmt = (
            select(Channel, ChannelMetric)
            .join(ChannelMetric, ChannelMetric.channel_id == Channel.id)
            .join(
                latest,
                (ChannelMetric.channel_id == latest.c.channel_id)
                & (ChannelMetric.collected_at == latest.c.max_collected_at),
            )
            .where(Channel.enabled.is_(True))
            .order_by(ChannelMetric.viewers.desc())
            .limit(limit)
        )
        return [(row[0], row[1]) for row in self._session.execute(stmt).all()]
