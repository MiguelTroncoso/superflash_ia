"""Tests del ciclo del adaptador compuesto: una consulta por fuente y pasada."""

from app.adapters.composite import CompositeMonitoringAdapter
from app.adapters.mock_sources import MockInfrastructureAdapter, MockStreamingAdapter
from app.collectors.collection import CollectionService
from tests.conftest import FIXED_NOW


def _fixed_clock():
    return FIXED_NOW


class _CountingInfrastructure(MockInfrastructureAdapter):
    """Cuenta cuántas veces se consulta cada método de la fuente."""

    def __init__(self) -> None:
        super().__init__(seed=42, now_fn=_fixed_clock)
        self.server_calls = 0
        self.metric_calls = 0

    def get_servers(self):  # type: ignore[override]
        self.server_calls += 1
        return super().get_servers()

    def get_infrastructure_metrics(self):  # type: ignore[override]
        self.metric_calls += 1
        return super().get_infrastructure_metrics()


class _CountingStreaming(MockStreamingAdapter):
    """Cuenta cuántas veces se consulta cada método de la fuente."""

    def __init__(self) -> None:
        super().__init__(seed=42, now_fn=_fixed_clock)
        self.channel_calls = 0
        self.metric_calls = 0

    def get_channels(self):  # type: ignore[override]
        self.channel_calls += 1
        return super().get_channels()

    def get_streaming_metrics(self):  # type: ignore[override]
        self.metric_calls += 1
        return super().get_streaming_metrics()


def test_each_source_queried_once_per_collection_cycle(session):
    """Una pasada completa de recolección consulta cada fuente UNA sola vez."""
    infrastructure = _CountingInfrastructure()
    streaming = _CountingStreaming()
    composite = CompositeMonitoringAdapter(infrastructure=infrastructure, streaming=streaming)

    result = CollectionService(session, composite).run()

    assert result.errors == []
    assert infrastructure.server_calls == 1
    assert infrastructure.metric_calls == 1
    assert streaming.channel_calls == 1
    assert streaming.metric_calls == 1


def test_cycle_snapshot_is_consistent_within_a_pass():
    """Servidores y canales de una pasada salen de la misma muestra."""
    composite = CompositeMonitoringAdapter(
        infrastructure=MockInfrastructureAdapter(seed=42, now_fn=_fixed_clock),
        streaming=MockStreamingAdapter(seed=42, now_fn=_fixed_clock),
    )
    composite.begin_collection_cycle()

    server_metrics = composite.get_server_metrics()
    channel_metrics = composite.get_channel_metrics()

    timestamps = {metric.collected_at for metric in server_metrics} | {
        metric.collected_at for metric in channel_metrics
    }
    assert len(timestamps) == 1, "toda la pasada comparte el mismo collected_at"

    # Los agregados derivados cuadran exactamente con la misma muestra.
    viewers_by_server: dict[str, int] = {}
    for metric in channel_metrics:
        assert metric.server_external_id is not None
        viewers_by_server[metric.server_external_id] = (
            viewers_by_server.get(metric.server_external_id, 0) + metric.viewers
        )
    for metric in server_metrics:
        assert metric.active_connections == viewers_by_server.get(metric.server_external_id, 0)


def test_begin_collection_cycle_refreshes_snapshot():
    """Un ciclo nuevo vuelve a consultar las fuentes (una vez cada una)."""
    infrastructure = _CountingInfrastructure()
    streaming = _CountingStreaming()
    composite = CompositeMonitoringAdapter(infrastructure=infrastructure, streaming=streaming)

    composite.begin_collection_cycle()
    composite.get_server_metrics()
    composite.get_channel_metrics()
    assert infrastructure.metric_calls == 1
    assert streaming.metric_calls == 1

    composite.begin_collection_cycle()
    composite.get_server_metrics()
    assert infrastructure.metric_calls == 2
    assert streaming.metric_calls == 2
