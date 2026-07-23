"""Tests del servicio de recolección: persistencia, deduplicación y errores."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.adapters.base import (
    ChannelMetricSnapshot,
    ChannelSnapshot,
    MonitoringSourceAdapter,
    ServerMetricSnapshot,
    ServerSnapshot,
)
from app.adapters.mock import MockMonitoringAdapter
from app.collectors.collection import CollectionService
from app.models import Channel, ChannelMetric, Server, ServerMetric
from tests.conftest import FIXED_NOW, TEST_API_KEY


def _run(session, now):
    adapter = MockMonitoringAdapter(seed=42, now_fn=lambda: now)
    return CollectionService(session, adapter).run()


def test_collection_persists_servers_and_channels(session):
    """Una recolección crea servidores y canales por external_id."""
    result = _run(session, FIXED_NOW)

    assert result.errors == []
    assert result.servers_synced >= 4
    assert result.channels_synced >= 20

    servers = list(session.scalars(select(Server)))
    channels = list(session.scalars(select(Channel)))
    assert len(servers) == result.servers_synced
    assert len(channels) == result.channels_synced
    assert all(server.external_id for server in servers)
    # Los canales quedan asociados a un servidor existente.
    server_ids = {server.id for server in servers}
    assert all(channel.current_server_id in server_ids for channel in channels)


def test_collection_persists_metrics(session):
    """Una recolección guarda una muestra por servidor y por canal."""
    result = _run(session, FIXED_NOW)

    assert result.server_metrics_inserted == result.servers_synced
    assert result.channel_metrics_inserted == result.channels_synced
    assert session.scalar(select(func.count()).select_from(ServerMetric)) == (
        result.server_metrics_inserted
    )
    assert session.scalar(select(func.count()).select_from(ChannelMetric)) == (
        result.channel_metrics_inserted
    )

    metric = session.scalars(select(ServerMetric)).first()
    assert metric is not None
    assert metric.source == "mock"
    assert 0 <= metric.cpu_percent <= 100


def test_collection_skips_duplicate_samples(session):
    """Repetir la recolección en el mismo minuto no duplica muestras."""
    first = _run(session, FIXED_NOW)
    second = _run(session, FIXED_NOW)

    assert second.server_metrics_inserted == 0
    assert second.channel_metrics_inserted == 0
    assert second.server_metrics_skipped == first.server_metrics_inserted
    assert second.channel_metrics_skipped == first.channel_metrics_inserted
    assert session.scalar(select(func.count()).select_from(ServerMetric)) == (
        first.server_metrics_inserted
    )


def test_collection_appends_new_samples_over_time(session):
    """Recolecciones en minutos distintos acumulan histórico."""
    first = _run(session, FIXED_NOW)
    second = _run(session, FIXED_NOW + timedelta(minutes=5))

    assert second.server_metrics_inserted == first.server_metrics_inserted
    total = session.scalar(select(func.count()).select_from(ServerMetric))
    assert total == first.server_metrics_inserted + second.server_metrics_inserted


class _FaultySourceAdapter(MonitoringSourceAdapter):
    """Fuente que mezcla datos válidos con referencias desconocidas."""

    _at = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)

    @property
    def source_name(self) -> str:
        return "faulty"

    def get_servers(self) -> list[ServerSnapshot]:
        return [ServerSnapshot(external_id="srv-ok", name="OK", network_capacity_mbps=1000)]

    def get_server_metrics(self) -> list[ServerMetricSnapshot]:
        valid = ServerMetricSnapshot(
            server_external_id="srv-ok",
            collected_at=self._at,
            cpu_percent=10,
            memory_percent=20,
            input_mbps=5,
            output_mbps=100,
            active_connections=50,
            active_streams=3,
        )
        unknown = valid.model_copy(update={"server_external_id": "srv-fantasma"})
        return [unknown, valid]

    def get_channels(self) -> list[ChannelSnapshot]:
        return [ChannelSnapshot(external_id="ch-ok", name="Canal OK", server_external_id="srv-ok")]

    def get_channel_metrics(self) -> list[ChannelMetricSnapshot]:
        valid = ChannelMetricSnapshot(
            channel_external_id="ch-ok",
            server_external_id="srv-ok",
            collected_at=self._at,
            viewers=120,
        )
        unknown = valid.model_copy(update={"channel_external_id": "ch-fantasma"})
        return [unknown, valid]


def test_collection_isolates_per_item_failures(session):
    """Un elemento desconocido no aborta el resto de la recolección."""
    result = CollectionService(session, _FaultySourceAdapter()).run()

    assert len(result.errors) == 2
    assert result.server_metrics_inserted == 1
    assert result.channel_metrics_inserted == 1
    assert session.scalar(select(func.count()).select_from(ServerMetric)) == 1
    assert session.scalar(select(func.count()).select_from(ChannelMetric)) == 1


def test_collection_endpoint_runs_mock(client):
    """POST /api/v1/collection/run genera y guarda datos simulados."""
    response = client.post("/api/v1/collection/run", headers={"X-API-Key": TEST_API_KEY})

    assert response.status_code == 200
    body = response.json()
    assert body["adapter"] == "mock"
    assert body["servers_synced"] >= 4
    assert body["channels_synced"] >= 20
    assert body["server_metrics_inserted"] >= 4

    servers = client.get("/api/v1/servers").json()
    assert len(servers) == body["servers_synced"]
