"""Selección de adaptadores de monitoreo según la configuración.

Punto único de extensión para fuentes reales. Cuando exista una (API del
panel, Prometheus, Netdata...), se registrará aquí bajo un nuevo valor de
``INFRASTRUCTURE_SOURCE`` o ``STREAMING_SOURCE``, leyendo sus credenciales
exclusivamente de variables de entorno declaradas en ``Settings`` — nunca
del código ni del repositorio. Ver docs/real-source-integration.md.
"""

from sqlalchemy.orm import Session

from app.adapters.base import MonitoringSourceAdapter, ServerSnapshot
from app.adapters.composite import CompositeMonitoringAdapter
from app.adapters.inventory import load_inventory
from app.adapters.mock import MockMonitoringAdapter
from app.adapters.mock_sources import MockInfrastructureAdapter, MockStreamingAdapter
from app.adapters.prometheus import PrometheusInfrastructureAdapter
from app.adapters.sources import InfrastructureMetricsAdapter, StreamingMetricsAdapter
from app.core.config import Settings
from app.repositories.server_repository import ServerRepository


def get_infrastructure_adapter(
    settings: Settings, session: Session | None = None
) -> InfrastructureMetricsAdapter:
    """Construye la fuente de infraestructura configurada.

    Raises:
        ValueError: Si el identificador configurado no está soportado o
            su configuración está incompleta o es inválida.
    """
    if settings.infrastructure_source == "mock":
        return MockInfrastructureAdapter(seed=settings.mock_seed)
    if settings.infrastructure_source == "prometheus":
        if session is not None:
            from app.adapters.prometheus import DatabasePrometheusInfrastructureAdapter

            servers = ServerRepository(session).list_enabled()
            fallback_servers = [
                ServerSnapshot(
                    external_id=server.external_id,
                    name=server.name,
                    hostname=server.hostname,
                    role=server.role,
                    network_capacity_mbps=server.network_capacity_mbps,
                    enabled=server.enabled,
                )
                for server in servers
                if not (server.prometheus_url and server.hostname)
            ]
            return DatabasePrometheusInfrastructureAdapter(
                servers,
                timeout_seconds=settings.prometheus_timeout_seconds,
                verify_tls=settings.prometheus_tls_verify,
                fallback=MockInfrastructureAdapter(
                    seed=settings.mock_seed,
                    server_snapshots=fallback_servers,
                )
                if fallback_servers
                else None,
            )
        if not settings.prometheus_url:
            raise ValueError("INFRASTRUCTURE_SOURCE=prometheus requiere PROMETHEUS_URL configurada")
        if not settings.infrastructure_inventory_file:
            raise ValueError(
                "INFRASTRUCTURE_SOURCE=prometheus requiere INFRASTRUCTURE_INVENTORY_FILE "
                "(inventario local, ver config/inventory.example.yaml)"
            )
        inventory = load_inventory(settings.infrastructure_inventory_file)
        return PrometheusInfrastructureAdapter(
            base_url=settings.prometheus_url,
            inventory=inventory,
            timeout_seconds=settings.prometheus_timeout_seconds,
            bearer_token=settings.prometheus_bearer_token,
            verify_tls=settings.prometheus_tls_verify,
        )
    raise ValueError(f"Fuente de infraestructura no soportada: {settings.infrastructure_source!r}")


def get_streaming_adapter(settings: Settings) -> StreamingMetricsAdapter:
    """Construye la fuente de streaming configurada.

    Raises:
        ValueError: Si el identificador configurado no está soportado.
    """
    if settings.streaming_source == "mock":
        return MockStreamingAdapter(seed=settings.mock_seed)
    raise ValueError(f"Fuente de streaming no soportada: {settings.streaming_source!r}")


def get_adapter(settings: Settings, session: Session | None = None) -> MonitoringSourceAdapter:
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
            infrastructure=get_infrastructure_adapter(settings, session),
            streaming=get_streaming_adapter(settings),
        )
    raise ValueError(f"Adaptador de monitoreo no soportado: {settings.monitoring_adapter!r}")
