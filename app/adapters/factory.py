"""Selección del adaptador de monitoreo según la configuración.

Punto único de extensión: cuando exista el adaptador del panel real se
registrará aquí (p. ej. ``"panel"``) leyendo sus credenciales desde
variables de entorno, nunca desde el código.
"""

from app.adapters.base import MonitoringSourceAdapter
from app.adapters.mock import MockMonitoringAdapter
from app.core.config import Settings


def get_adapter(settings: Settings) -> MonitoringSourceAdapter:
    """Construye el adaptador configurado en ``MONITORING_ADAPTER``.

    Raises:
        ValueError: Si el identificador configurado no está soportado.
    """
    if settings.monitoring_adapter == "mock":
        return MockMonitoringAdapter(seed=settings.mock_seed)
    raise ValueError(f"Adaptador de monitoreo no soportado: {settings.monitoring_adapter!r}")
