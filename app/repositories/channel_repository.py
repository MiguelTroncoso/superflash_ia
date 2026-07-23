"""Acceso a datos de canales y sus métricas."""

from datetime import datetime

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from app.adapters.base import ChannelSnapshot
from app.models.channel import Channel, ChannelMetric


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

    def get(self, channel_id: int) -> Channel | None:
        """Busca un canal por su id interno."""
        return self._session.get(Channel, channel_id)

    def get_by_external_id(self, external_id: str) -> Channel | None:
        """Busca un canal por su identificador externo."""
        stmt = select(Channel).where(Channel.external_id == external_id)
        return self._session.scalars(stmt).first()

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
