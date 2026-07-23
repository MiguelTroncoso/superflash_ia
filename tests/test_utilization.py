"""Tests unitarios del cálculo de utilización de red."""

import pytest

from app.services.overview_service import compute_network_utilization


def test_normal_utilization():
    """output/capacidad*100 con redondeo a dos decimales."""
    assert compute_network_utilization(500.0, 1000.0) == 50.0
    assert compute_network_utilization(333.0, 1000.0) == 33.3
    assert compute_network_utilization(1.0, 3.0) == 33.33


@pytest.mark.parametrize("capacity", [0.0, -10.0, None])
def test_unusable_capacity_returns_none(capacity):
    """Capacidad nula, cero o negativa no permite calcular utilización."""
    assert compute_network_utilization(500.0, capacity) is None


def test_zero_output():
    """Sin tráfico de salida la utilización es 0%."""
    assert compute_network_utilization(0.0, 1000.0) == 0.0


def test_over_capacity():
    """Se admite y refleja una utilización superior al 100%."""
    assert compute_network_utilization(1500.0, 1000.0) == 150.0
