"""Tests de los contratos por tipo de fuente, sus mocks y el compuesto."""

from sqlalchemy import func, select

from app.adapters.composite import CompositeMonitoringAdapter
from app.adapters.factory import (
    get_adapter,
    get_infrastructure_adapter,
    get_streaming_adapter,
)
from app.adapters.mock import MockMonitoringAdapter
from app.adapters.mock_sources import MockInfrastructureAdapter, MockStreamingAdapter
from app.collectors.collection import CollectionService
from app.models import ChannelMetric, ServerMetric
from tests.conftest import FIXED_NOW, make_test_settings


def _fixed_clock():
    return FIXED_NOW


def _composite():
    return CompositeMonitoringAdapter(
        infrastructure=MockInfrastructureAdapter(seed=42, now_fn=_fixed_clock),
        streaming=MockStreamingAdapter(seed=42, now_fn=_fixed_clock),
    )


# --- Fuente de infraestructura -------------------------------------------------


def test_infrastructure_mock_inventory_and_fields():
    """El mock de infraestructura entrega servidores y todos los campos nuevos."""
    adapter = MockInfrastructureAdapter(seed=42, now_fn=_fixed_clock)

    assert len(adapter.get_servers()) >= 4
    metrics = adapter.get_infrastructure_metrics()
    assert len(metrics) >= 4
    for metric in metrics:
        assert 0 <= metric.cpu_percent <= 100
        assert 0 <= metric.memory_percent <= 100
        assert metric.disk_percent is not None and 0 <= metric.disk_percent <= 100
        assert metric.input_mbps >= 0
        assert metric.output_mbps >= 0
        assert metric.load_average_1m is not None and metric.load_average_1m >= 0
        assert metric.load_average_5m is not None
        assert metric.load_average_15m is not None
        assert metric.uptime_seconds is not None and metric.uptime_seconds > 0
        assert metric.status.value in {"online", "degraded", "offline", "unknown"}


def test_infrastructure_mock_is_reproducible():
    """Misma semilla y mismo minuto → misma muestra de infraestructura."""
    first = MockInfrastructureAdapter(seed=7, now_fn=_fixed_clock)
    second = MockInfrastructureAdapter(seed=7, now_fn=_fixed_clock)
    assert first.get_infrastructure_metrics() == second.get_infrastructure_metrics()


def test_infrastructure_mock_matches_legacy_mock():
    """CPU/RAM/red coinciden con el mock combinado: mismo mundo simulado."""
    legacy = {
        metric.server_external_id: metric
        for metric in MockMonitoringAdapter(seed=42, now_fn=_fixed_clock).get_server_metrics()
    }
    for metric in MockInfrastructureAdapter(
        seed=42, now_fn=_fixed_clock
    ).get_infrastructure_metrics():
        base = legacy[metric.server_external_id]
        assert metric.cpu_percent == base.cpu_percent
        assert metric.memory_percent == base.memory_percent
        assert metric.output_mbps == base.output_mbps
        assert metric.input_mbps == base.input_mbps


# --- Fuente de streaming -------------------------------------------------------


def test_streaming_mock_inventory_and_fields():
    """El mock de streaming entrega canales, espectadores, bitrate y estado."""
    adapter = MockStreamingAdapter(seed=42, now_fn=_fixed_clock)

    assert len(adapter.get_channels()) >= 20
    metrics = adapter.get_streaming_metrics()
    assert len(metrics) >= 20
    viewers = [metric.viewers for metric in metrics]
    assert max(viewers) > 300 and min(viewers) < 150, "audiencias variadas"
    for metric in metrics:
        assert metric.viewers >= 0
        assert metric.bitrate_mbps is None or metric.bitrate_mbps >= 0
        assert metric.status.value in {"online", "degraded", "offline", "unknown"}


def test_streaming_mock_is_reproducible():
    """Misma semilla y mismo minuto → misma muestra de streaming."""
    first = MockStreamingAdapter(seed=7, now_fn=_fixed_clock)
    second = MockStreamingAdapter(seed=7, now_fn=_fixed_clock)
    assert first.get_streaming_metrics() == second.get_streaming_metrics()


# --- Adaptador compuesto -------------------------------------------------------


def test_composite_derives_connections_from_streaming():
    """Las conexiones por servidor son la suma de espectadores de sus canales."""
    composite = _composite()

    expected_viewers: dict[str, int] = {}
    for metric in MockStreamingAdapter(seed=42, now_fn=_fixed_clock).get_streaming_metrics():
        assert metric.server_external_id is not None
        expected_viewers[metric.server_external_id] = (
            expected_viewers.get(metric.server_external_id, 0) + metric.viewers
        )

    for server_metric in composite.get_server_metrics():
        assert server_metric.active_connections == expected_viewers.get(
            server_metric.server_external_id, 0
        )


def test_composite_estimates_channel_output():
    """El output estimado de cada canal es viewers * bitrate."""
    for metric in _composite().get_channel_metrics():
        if metric.bitrate_mbps is not None:
            assert metric.estimated_output_mbps == round(metric.viewers * metric.bitrate_mbps, 2)


def test_composite_feeds_collection_service(session):
    """CollectionService persiste sin cambios usando el adaptador compuesto."""
    result = CollectionService(session, _composite()).run()

    assert result.errors == []
    assert result.adapter == "mock-infra+mock-streaming"
    assert result.servers_synced >= 4
    assert result.channels_synced >= 20
    assert session.scalar(select(func.count()).select_from(ServerMetric)) == result.servers_synced
    assert session.scalar(select(func.count()).select_from(ChannelMetric)) == result.channels_synced
    stored = session.scalars(select(ServerMetric)).first()
    assert stored is not None
    assert stored.source == "mock-infra+mock-streaming"


# --- Fábrica -------------------------------------------------------------------


def test_factory_builds_source_adapters():
    """La fábrica construye las fuentes configuradas y el modo composite."""
    settings = make_test_settings()
    assert isinstance(get_infrastructure_adapter(settings), MockInfrastructureAdapter)
    assert isinstance(get_streaming_adapter(settings), MockStreamingAdapter)
    assert isinstance(get_adapter(settings), MockMonitoringAdapter)

    composite_settings = make_test_settings(monitoring_adapter="composite")
    assert isinstance(get_adapter(composite_settings), CompositeMonitoringAdapter)
