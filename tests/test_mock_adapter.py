"""Tests del adaptador de datos simulados."""

from app.adapters.mock import MockMonitoringAdapter
from tests.conftest import FIXED_NOW


def _fixed_clock():
    return FIXED_NOW


def test_minimum_inventory():
    """El mock entrega al menos cuatro servidores y veinte canales."""
    adapter = MockMonitoringAdapter(seed=42, now_fn=_fixed_clock)

    servers = adapter.get_servers()
    channels = adapter.get_channels()

    assert len(servers) >= 4
    assert len(channels) >= 20
    capacities = {server.network_capacity_mbps for server in servers}
    assert len(capacities) > 1, "debe haber capacidades de red diferentes"


def test_reproducible_with_same_seed():
    """Misma semilla y mismo instante producen exactamente la misma muestra."""
    first = MockMonitoringAdapter(seed=7, now_fn=_fixed_clock)
    second = MockMonitoringAdapter(seed=7, now_fn=_fixed_clock)

    assert first.get_server_metrics() == second.get_server_metrics()
    assert first.get_channel_metrics() == second.get_channel_metrics()


def test_different_seed_changes_sample():
    """Semillas distintas producen muestras distintas."""
    first = MockMonitoringAdapter(seed=1, now_fn=_fixed_clock)
    second = MockMonitoringAdapter(seed=2, now_fn=_fixed_clock)

    assert first.get_channel_metrics() != second.get_channel_metrics()


def test_audience_variety():
    """Algunos canales tienen bastante más audiencia que otros."""
    adapter = MockMonitoringAdapter(seed=42, now_fn=_fixed_clock)
    viewers = [metric.viewers for metric in adapter.get_channel_metrics()]

    assert max(viewers) > 300
    assert min(viewers) < 150
    assert len(set(viewers)) > 10, "las audiencias no deben ser uniformes"


def test_metrics_within_valid_ranges():
    """CPU y memoria simuladas se mantienen en rangos razonables."""
    adapter = MockMonitoringAdapter(seed=42, now_fn=_fixed_clock)

    for metric in adapter.get_server_metrics():
        assert 0 <= metric.cpu_percent <= 100
        assert 0 <= metric.memory_percent <= 100
        assert metric.output_mbps >= 0
        assert metric.input_mbps >= 0
