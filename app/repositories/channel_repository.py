"""Acceso a datos de canales, ciclo de vida y métricas."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.adapters.base import ChannelSnapshot
from app.core.timeutils import ensure_utc
from app.models.channel import (
    Channel,
    ChannelCategoryHistory,
    ChannelEvent,
    ChannelMetric,
    ChannelType,
    TechnicalStream,
)
from app.models.server import Server


@dataclass(frozen=True)
class ChannelSyncOutcome:
    """Resultado de sincronizar una fila de canal."""

    channel: Channel
    action: str


@dataclass(frozen=True)
class ChannelReconciliationResult:
    """Resultado de reconciliar ausencias de una fuente."""

    deactivated: int = 0
    archived: int = 0


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
        category_id: str | None = None,
        source_id: str | None = None,
        channel_type: ChannelType | None = None,
        active: bool | None = None,
        event_start_from: datetime | None = None,
        event_start_to: datetime | None = None,
        enabled: bool | None = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> tuple[
        list[
            tuple[
                Channel,
                Server | None,
                ChannelMetric | None,
                ChannelEvent | None,
                TechnicalStream | None,
            ]
        ],
        int,
    ]:
        """Devuelve una página agregada sin consultas por evento o stream."""
        filters = self._page_filters(
            search=search,
            server_id=server_id,
            category=category,
            category_id=category_id,
            source_id=source_id,
            channel_type=channel_type,
            active=active,
            event_start_from=event_start_from,
            event_start_to=event_start_to,
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
            select(Channel, Server, ChannelMetric, ChannelEvent, TechnicalStream)
            .select_from(Channel)
            .outerjoin(Server, Channel.current_server_id == Server.id)
            .outerjoin(ChannelEvent, Channel.event_id == ChannelEvent.id)
            .outerjoin(TechnicalStream, Channel.technical_stream_id == TechnicalStream.id)
            .outerjoin(latest, latest.c.channel_id == Channel.id)
            .outerjoin(ChannelMetric, metric_join)
            .where(*filters)
            .order_by(*self._sort_expressions(sort_by, sort_order))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = [
            (row[0], row[1], row[2], row[3], row[4]) for row in self._session.execute(stmt).all()
        ]
        return rows, int(total)

    @staticmethod
    def _page_filters(
        *,
        search: str | None,
        server_id: int | None,
        category: str | None,
        category_id: str | None,
        source_id: str | None,
        channel_type: ChannelType | None,
        active: bool | None,
        event_start_from: datetime | None,
        event_start_to: datetime | None,
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
        if category_id is not None:
            filters.append(Channel.category_id == category_id)
        if source_id is not None:
            filters.append(Channel.source_id == source_id)
        if channel_type is not None:
            filters.append(Channel.channel_type == channel_type)
        if active is not None:
            filters.append(Channel.active.is_(active))
        if event_start_from is not None:
            filters.append(Channel.event_start_at >= event_start_from)
        if event_start_to is not None:
            filters.append(Channel.event_start_at <= event_start_to)
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
        """Busca un canal por external_id para consumidores legacy.

        Las nuevas rutas de sincronización siempre usan ``source_id``. Este
        método queda para compatibilidad con callers antiguos y solo debe
        usarse cuando la fuente no puede aportar identidad compuesta.
        """
        stmt = select(Channel).where(Channel.external_id == external_id).order_by(Channel.id)
        return self._session.scalars(stmt).first()

    def get_by_identity(self, source_id: str, external_id: str) -> Channel | None:
        """Busca un canal por la identidad estable de su fuente."""
        stmt = select(Channel).where(
            Channel.source_id == source_id,
            Channel.external_id == external_id,
        )
        return self._session.scalars(stmt).first()

    def get_by_identities(self, identities: set[tuple[str, str]]) -> dict[tuple[str, str], Channel]:
        """Carga canales por identidad compuesta agrupando por fuente."""
        by_source: dict[str, set[str]] = defaultdict(set)
        for source_id, external_id in identities:
            by_source[source_id].add(external_id)
        found: dict[tuple[str, str], Channel] = {}
        for source_id, external_ids in by_source.items():
            stmt = select(Channel).where(
                Channel.source_id == source_id,
                Channel.external_id.in_(external_ids),
            )
            for channel in self._session.scalars(stmt):
                found[(source_id, channel.external_id)] = channel
        return found

    def get_events_by_identities(
        self, identities: set[tuple[str, str]]
    ) -> dict[tuple[str, str], ChannelEvent]:
        """Carga eventos por identidad compuesta, sin consultas por métrica."""
        by_source: dict[str, set[str]] = defaultdict(set)
        for source_id, external_id in identities:
            by_source[source_id].add(external_id)
        found: dict[tuple[str, str], ChannelEvent] = {}
        for source_id, external_ids in by_source.items():
            stmt = select(ChannelEvent).where(
                ChannelEvent.source_id == source_id,
                ChannelEvent.external_id.in_(external_ids),
            )
            for event in self._session.scalars(stmt):
                found[(source_id, event.external_id)] = event
        return found

    def get_streams_by_identities(
        self, identities: set[tuple[str, str]]
    ) -> dict[tuple[str, str], TechnicalStream]:
        """Carga streams técnicos por identidad compuesta."""
        by_source: dict[str, set[str]] = defaultdict(set)
        for source_id, external_id in identities:
            by_source[source_id].add(external_id)
        found: dict[tuple[str, str], TechnicalStream] = {}
        for source_id, external_ids in by_source.items():
            stmt = select(TechnicalStream).where(
                TechnicalStream.source_id == source_id,
                TechnicalStream.external_id.in_(external_ids),
            )
            for stream in self._session.scalars(stmt):
                found[(source_id, stream.external_id)] = stream
        return found

    def count(self) -> int:
        """Cuenta los canales registrados."""
        return int(self._session.scalar(select(func.count(Channel.id))) or 0)

    def upsert_from_snapshot(
        self,
        snapshot: ChannelSnapshot,
        current_server_id: int | None,
        source_id: str,
        seen_at: datetime,
    ) -> ChannelSyncOutcome:
        """Crea o actualiza un canal por ``source_id + external_id``."""
        identity_source = snapshot.source_id or source_id
        channel = self.get_by_identity(identity_source, snapshot.external_id)
        adopted_legacy = False
        if channel is None:
            # 0009 backfills existing rows as ``legacy``. Adopt the unique
            # legacy row on first observation instead of duplicating it.
            channel = self._session.scalars(
                select(Channel).where(
                    Channel.source_id == "legacy",
                    Channel.external_id == snapshot.external_id,
                )
            ).first()
            adopted_legacy = channel is not None
        is_new = channel is None
        was_inactive = bool(channel is not None and not channel.active)
        if channel is None:
            channel = Channel(
                source_id=identity_source,
                external_id=snapshot.external_id,
                first_seen_at=seen_at,
            )
            self._session.add(channel)
        before = self._channel_values(channel)

        if adopted_legacy:
            channel.source_id = identity_source
        channel.name = snapshot.name
        channel.category = snapshot.category
        channel.category_id = snapshot.category_id
        channel.channel_type = snapshot.channel_type
        channel.event_start_at = snapshot.event_start_at
        channel.event_end_at = snapshot.event_end_at
        channel.current_server_id = current_server_id
        channel.enabled = snapshot.enabled
        channel.active = True
        channel.inactive_since_at = None
        channel.archived_at = None
        channel.last_seen_at = seen_at
        channel.source_updated_at = snapshot.source_updated_at

        event = self._upsert_event(snapshot, identity_source, seen_at)
        stream = self._upsert_stream(snapshot, identity_source, seen_at)
        channel.event_id = event.id if event is not None else None
        channel.technical_stream_id = stream.id if stream is not None else None
        self._session.flush()
        self._record_category_change(channel, identity_source, seen_at)
        self._session.flush()

        if is_new:
            action = "created"
        elif was_inactive:
            action = "reactivated"
        elif before != self._channel_values(channel) or adopted_legacy:
            action = "updated"
        else:
            action = "unchanged"
        return ChannelSyncOutcome(channel=channel, action=action)

    @staticmethod
    def _channel_values(channel: Channel) -> tuple[object, ...]:
        """Extrae campos que determinan si una sincronización cambió datos."""
        values = (
            channel.source_id,
            channel.name,
            channel.category,
            channel.category_id,
            channel.channel_type,
            channel.event_start_at,
            channel.event_end_at,
            channel.current_server_id,
            channel.event_id,
            channel.technical_stream_id,
            channel.enabled,
            channel.active,
            channel.archived_at,
            channel.source_updated_at,
        )
        return tuple(
            ensure_utc(value) if isinstance(value, datetime) else value for value in values
        )

    def _upsert_event(
        self, snapshot: ChannelSnapshot, source_id: str, seen_at: datetime
    ) -> ChannelEvent | None:
        """Sincroniza el evento concreto si la fuente lo identifica."""
        if snapshot.event_external_id is None:
            return None
        event = self._session.scalars(
            select(ChannelEvent).where(
                ChannelEvent.source_id == source_id,
                ChannelEvent.external_id == snapshot.event_external_id,
            )
        ).first()
        if event is None:
            event = ChannelEvent(
                source_id=source_id,
                external_id=snapshot.event_external_id,
                name=snapshot.event_name or snapshot.name,
                first_seen_at=seen_at,
            )
            self._session.add(event)
        event.name = snapshot.event_name or snapshot.name
        event.category_id = snapshot.category_id
        event.category_name = snapshot.category
        event.event_start_at = snapshot.event_start_at
        event.event_end_at = snapshot.event_end_at
        event.last_seen_at = seen_at
        event.active = True
        event.archived_at = None
        self._session.flush()
        return event

    def _upsert_stream(
        self, snapshot: ChannelSnapshot, source_id: str, seen_at: datetime
    ) -> TechnicalStream | None:
        """Sincroniza un stream técnico reutilizable."""
        if snapshot.technical_stream_external_id is None:
            return None
        stream = self._session.scalars(
            select(TechnicalStream).where(
                TechnicalStream.source_id == source_id,
                TechnicalStream.external_id == snapshot.technical_stream_external_id,
            )
        ).first()
        if stream is None:
            stream = TechnicalStream(
                source_id=source_id,
                external_id=snapshot.technical_stream_external_id,
                first_seen_at=seen_at,
            )
            self._session.add(stream)
        stream.name = snapshot.technical_stream_name
        stream.last_seen_at = seen_at
        stream.active = True
        self._session.flush()
        return stream

    def _record_category_change(self, channel: Channel, source_id: str, seen_at: datetime) -> None:
        """Cierra el intervalo anterior y abre uno si cambió la categoría."""
        latest = self._session.scalars(
            select(ChannelCategoryHistory)
            .where(ChannelCategoryHistory.channel_id == channel.id)
            .order_by(ChannelCategoryHistory.valid_from.desc(), ChannelCategoryHistory.id.desc())
            .limit(1)
        ).first()
        current = (channel.category_id, channel.category)
        previous = (latest.category_id, latest.category_name) if latest is not None else None
        if latest is not None and previous == current:
            latest.valid_to = None
            return
        if latest is not None and latest.valid_to is None:
            latest.valid_to = seen_at
        self._session.add(
            ChannelCategoryHistory(
                channel_id=channel.id,
                source_id=source_id,
                category_id=channel.category_id,
                category_name=channel.category,
                valid_from=seen_at,
            )
        )
        self._session.flush()

    def reconcile_missing(
        self,
        *,
        source_id: str,
        seen_external_ids: set[str],
        observed_at: datetime,
        event_inactive_grace_hours: int,
        event_archive_days: int,
        permanent_archive_days: int,
    ) -> ChannelReconciliationResult:
        """Desactiva ausentes y archiva solo tras las retenciones configuradas."""
        channels = list(
            self._session.scalars(select(Channel).where(Channel.source_id == source_id))
        )
        deactivated = 0
        archived = 0
        for channel in channels:
            if channel.external_id not in seen_external_ids and channel.active:
                channel.active = False
                channel.enabled = False
                channel.current_server_id = None
                channel.inactive_since_at = observed_at
                deactivated += 1

        grace_cutoff = observed_at - timedelta(hours=event_inactive_grace_hours)
        for channel in channels:
            if channel.active or channel.archived_at is not None:
                continue
            inactive_since = ensure_utc(channel.inactive_since_at or channel.last_seen_at)
            retention_days = (
                permanent_archive_days
                if channel.channel_type is ChannelType.PERMANENT
                else event_archive_days
            )
            archive_cutoff = observed_at - timedelta(days=retention_days)
            if (
                inactive_since <= grace_cutoff
                and ensure_utc(channel.last_seen_at) <= archive_cutoff
            ):
                channel.channel_type = ChannelType.ARCHIVED
                channel.archived_at = observed_at
                archived += 1

        self._session.flush()
        return ChannelReconciliationResult(deactivated=deactivated, archived=archived)

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
