"""Adaptadores de fuentes externas de monitoreo.

Aquí viven la interfaz ``MonitoringSourceAdapter`` y sus
implementaciones. La única implementación actual es
``MockMonitoringAdapter`` (datos simulados). El adaptador para el panel
real se implementará en un módulo futuro (p. ej. ``panel.py``) sin
cambiar el resto de la aplicación.
"""

from app.adapters.base import MonitoringSourceAdapter
from app.adapters.factory import get_adapter
from app.adapters.mock import MockMonitoringAdapter

__all__ = ["MockMonitoringAdapter", "MonitoringSourceAdapter", "get_adapter"]
