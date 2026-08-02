"""Ciclo de vida idempotente para canales dinámicos y eventos."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.adapters.base import (
    ChannelMetricSnapshot,
    ChannelSnapshot,
    MonitoringSourceAdapter,
    ServerMetricSnapshot,
    ServerSnapshot,
)
from app.collectors.collection import CollectionService
from app.models import (
    Channel,
    ChannelCategoryHistory,
    ChannelEvent,
    ChannelMetric,
    ChannelType,
    TechnicalStream,
)


class _DynamicAdapter(MonitoringSourceAdapter):
    """Fuente Xtream mínima y mutable para probar sincronizaciones sucesivas."""

    source = "xtream:provider-a"

    def __init__(self) -> None:
        self.now = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
        self.channels: list[ChannelSnapshot] = []

    @property
    def source_name(self) -> str:
        return self.source

    def get_servers(self) -> list[ServerSnapshot]:
        return [
            ServerSnapshot(
                external_id="srv-live",
                name="Live",
                network_capacity_mbps=1000,
            )
        ]

    def get_server_metrics(self) -> list[ServerMetricSnapshot]:
        return [
            ServerMetricSnapshot(
                server_external_id="srv-live",
                collected_at=self.now,
                cpu_percent=20,
                memory_percent=30,
                input_mbps=10,
                output_mbps=20,
                active_connections=10,
                active_streams=len(self.channels),
            )
        ]

    def get_channels(self) -> list[ChannelSnapshot]:
        return list(self.channels)

    def get_channel_metrics(self) -> list[ChannelMetricSnapshot]:
        return [
            ChannelMetricSnapshot(
                channel_external_id=channel.external_id,
                source_id=channel.source_id,
                server_external_id="srv-live",
                event_external_id=channel.event_external_id,
                technical_stream_external_id=channel.technical_stream_external_id,
                collected_at=self.now,
                viewers=100,
                bitrate_mbps=4,
                estimated_output_mbps=400,
            )
            for channel in self.channels
        ]


def _event_channel(
    *,
    external_id: str = "stream-1",
    name: str = "Match A",
    category: str = "Sports",
    category_id: str = "sports",
) -> ChannelSnapshot:
    return ChannelSnapshot(
        source_id=_DynamicAdapter.source,
        external_id=external_id,
        name=name,
        category=category,
        category_id=category_id,
        server_external_id="srv-live",
        channel_type=ChannelType.EVENT,
        event_external_id="event-1",
        event_name="Team A vs Team B",
        event_start_at=datetime(2026, 8, 2, 18, 0, tzinfo=UTC),
        event_end_at=datetime(2026, 8, 2, 20, 0, tzinfo=UTC),
        technical_stream_external_id="technical-1",
        technical_stream_name="Live feed 1",
    )


def _run(session, adapter: _DynamicAdapter):
    return CollectionService(
        session,
        adapter,
        event_inactive_grace_hours=0,
        event_archive_days=1,
        permanent_archive_days=2,
        now_fn=lambda: adapter.now,
    ).run()


def test_event_lifecycle_is_idempotent_and_preserves_history(session):
    adapter = _DynamicAdapter()
    adapter.channels = [_event_channel()]

    first = _run(session, adapter)
    channel = session.scalars(select(Channel)).one()
    channel_id = channel.id
    assert first.channels_created == 1
    assert first.channels_reactivated == 0
    assert session.scalar(select(func.count()).select_from(ChannelEvent)) == 1
    assert session.scalar(select(func.count()).select_from(TechnicalStream)) == 1

    repeated = _run(session, adapter)
    assert repeated.channels_unchanged == 1
    assert repeated.channels_created == 0
    assert session.scalar(select(func.count()).select_from(Channel)) == 1

    adapter.channels = [_event_channel(name="Match A renamed", category="Live Events")]
    updated = _run(session, adapter)
    assert updated.channels_updated == 1
    assert session.get(Channel, channel_id).name == "Match A renamed"
    history = list(
        session.scalars(
            select(ChannelCategoryHistory).where(ChannelCategoryHistory.channel_id == channel_id)
        )
    )
    assert len(history) == 2
    assert {item.category_name for item in history} == {"Sports", "Live Events"}

    adapter.channels = []
    adapter.now += timedelta(hours=1)
    missing = _run(session, adapter)
    channel = session.get(Channel, channel_id)
    assert missing.channels_deactivated == 1
    assert channel is not None and channel.active is False
    assert channel.archived_at is None

    adapter.channels = [_event_channel(name="Match A back")]
    adapter.now += timedelta(hours=1)
    reactivated = _run(session, adapter)
    channel = session.get(Channel, channel_id)
    assert reactivated.channels_reactivated == 1
    assert channel is not None and channel.id == channel_id and channel.active is True
    assert channel.archived_at is None


def test_same_name_with_different_external_id_creates_distinct_channels(session):
    adapter = _DynamicAdapter()
    adapter.channels = [
        _event_channel(external_id="stream-1", name="Sports Event"),
        _event_channel(external_id="stream-2", name="Sports Event"),
    ]

    result = _run(session, adapter)

    assert result.channels_created == 2
    assert session.scalar(select(func.count()).select_from(Channel)) == 2
    assert {channel.external_id for channel in session.scalars(select(Channel))} == {
        "stream-1",
        "stream-2",
    }


def test_missing_event_is_archived_after_retention_without_deleting_metrics(session):
    adapter = _DynamicAdapter()
    adapter.channels = [_event_channel()]
    _run(session, adapter)
    channel = session.scalars(select(Channel)).one()
    metric_count = session.scalar(select(func.count()).select_from(ChannelMetric))

    adapter.channels = []
    adapter.now += timedelta(days=2)
    result = _run(session, adapter)

    channel = session.get(Channel, channel.id)
    assert result.channels_deactivated == 1
    assert result.channels_archived == 1
    assert channel is not None
    assert channel.channel_type is ChannelType.ARCHIVED
    assert channel.active is False
    assert session.scalar(select(func.count()).select_from(ChannelMetric)) == metric_count
