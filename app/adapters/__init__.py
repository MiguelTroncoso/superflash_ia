"""Adaptadores de fuentes externas de monitoreo.

Contratos disponibles:

- ``MonitoringSourceAdapter`` (``base.py``): contrato combinado que
  consume el pipeline de recolección.
- ``InfrastructureMetricsAdapter`` y ``StreamingMetricsAdapter``
  (``sources.py``): contratos por tipo de fuente para integraciones
  reales; ``CompositeMonitoringAdapter`` los une hacia el contrato
  combinado.

Implementaciones actuales: exclusivamente mocks (datos simulados). Las
fuentes reales se registrarán en ``factory.py`` sin tocar el resto de la
aplicación; ver docs/real-source-integration.md.
"""

from app.adapters.base import MonitoringSourceAdapter
from app.adapters.composite import CompositeMonitoringAdapter
from app.adapters.factory import (
    get_adapter,
    get_infrastructure_adapter,
    get_streaming_adapter,
)
from app.adapters.mock import MockMonitoringAdapter
from app.adapters.mock_sources import MockInfrastructureAdapter, MockStreamingAdapter
from app.adapters.sources import InfrastructureMetricsAdapter, StreamingMetricsAdapter

__all__ = [
    "CompositeMonitoringAdapter",
    "InfrastructureMetricsAdapter",
    "MockInfrastructureAdapter",
    "MockMonitoringAdapter",
    "MockStreamingAdapter",
    "MonitoringSourceAdapter",
    "StreamingMetricsAdapter",
    "get_adapter",
    "get_infrastructure_adapter",
    "get_streaming_adapter",
]
