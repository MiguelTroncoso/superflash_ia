"""Selección de adaptadores de monitoreo según la configuración.

Punto único de extensión para fuentes reales. Cuando exista una (API del
panel, Prometheus, Netdata...), se registrará aquí bajo un nuevo valor de
``INFRASTRUCTURE_SOURCE`` o ``STREAMING_SOURCE``, leyendo sus credenciales
exclusivamente de variables de entorno declaradas en ``Settings`` — nunca
del código ni del repositorio. Ver docs/real-source-integration.md.
"""

from app.adapters.base import MonitoringSourceAdapter
from app.adapters.composite import CompositeMonitoringAdapter
from app.adapters.mock import MockMonitoringAdapter
from app.adapters.mock_sources import MockInfrastructureAdapter, MockStreamingAdapter
from app.adapters.sources import InfrastructureMetricsAdapter, StreamingMetricsAdapter
from app.core.config import Settings


def get_infrastructure_adapter(settings: Settings) -> InfrastructureMetricsAdapter:
    """Construye la fuente de infraestructura configurada.

    Raises:
        ValueError: Si el identificador configurado no está soportado.
    """
    if settings.infrastructure_source == "mock":
        return MockInfrastructureAdapter(seed=settings.mock_seed)
    raise ValueError(f"Fuente de infraestructura no soportada: {settings.infrastructure_source!r}")


def get_streaming_adapter(settings: Settings) -> StreamingMetricsAdapter:
    """Construye la fuente de streaming configurada.

    Raises:
        ValueError: Si el identificador configurado no está soportado.
    """
    if settings.streaming_source == "mock":
        return MockStreamingAdapter(seed=settings.mock_seed)
    raise ValueError(f"Fuente de streaming no soportada: {settings.streaming_source!r}")


def get_adapter(settings: Settings) -> MonitoringSourceAdapter:
    """Construye el adaptador que alimenta la recolección.

    - ``mock`` (por defecto): el adaptador combinado histórico.
    - ``composite``: une las fuentes de infraestructura y streaming
      configuradas; con ambas en ``mock`` produce el mismo mundo simulado.

    Raises:
        ValueError: Si el identificador configurado no está soportado.
    """
    if settings.monitoring_adapter == "mock":
        return MockMonitoringAdapter(seed=settings.mock_seed)
    if settings.monitoring_adapter == "composite":
        return CompositeMonitoringAdapter(
            infrastructure=get_infrastructure_adapter(settings),
            streaming=get_streaming_adapter(settings),
        )
    raise ValueError(f"Adaptador de monitoreo no soportado: {settings.monitoring_adapter!r}")
