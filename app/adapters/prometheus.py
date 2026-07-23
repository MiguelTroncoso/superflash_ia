"""Fuente de infraestructura real: Prometheus + node_exporter.

Consulta la API HTTP de Prometheus (``GET /api/v1/query``, únicamente
solicitudes GET de solo lectura) y normaliza las métricas estándar de
node_exporter al contrato ``InfrastructureMetricsAdapter``. Los
servidores a monitorear provienen de un inventario local no versionado
(``app/adapters/inventory.py``).

Seguridad:

- La URL y el token llegan solo por configuración; el token viaja en la
  cabecera ``Authorization`` y JAMÁS se escribe en logs ni en errores.
- TLS se verifica por defecto y no puede desactivarse en producción
  (validado en ``Settings``).
- Un fallo en un host no impide recolectar los demás; si TODOS fallan se
  lanza ``PrometheusSourceError`` para que la ejecución quede en error.
- Los hosts con ``up == 0`` o sin métricas esenciales no emiten muestra
  (no se fabrican ceros); la alerta de servidor sin muestra reciente los
  hará visibles.
"""

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from app.adapters.base import ServerSnapshot
from app.adapters.inventory import Inventory, InventoryServer
from app.adapters.sources import (
    InfrastructureMetricsAdapter,
    InfrastructureMetricSnapshot,
    ServerStatus,
)

logger = logging.getLogger(__name__)

_QUERY_PATH = "/api/v1/query"

# Filtros estándar: descartar pseudo-sistemas de archivos e interfaces
# virtuales para que disco y red reflejen el hardware real.
_FS_FILTER = 'fstype!~"tmpfs|overlay|squashfs|ramfs"'
_NIC_FILTER = 'device!~"lo|veth.*|docker.*|br-.*"'

_ESSENTIAL_METRICS = ("cpu_percent", "memory_percent", "input_mbps", "output_mbps")


class PrometheusSourceError(RuntimeError):
    """Prometheus no está disponible o rechazó las consultas."""


class PrometheusAuthError(PrometheusSourceError):
    """Prometheus rechazó las credenciales (401/403)."""


def build_queries(instance: str) -> dict[str, str]:
    """Consultas PromQL de node_exporter para una instancia del inventario."""
    i = f'instance="{instance}"'
    return {
        "up": f"max(up{{{i}}})",
        "cpu_percent": (f'100 * (1 - avg(rate(node_cpu_seconds_total{{mode="idle",{i}}}[5m])))'),
        "memory_percent": (
            f"100 * (1 - (node_memory_MemAvailable_bytes{{{i}}} "
            f"/ node_memory_MemTotal_bytes{{{i}}}))"
        ),
        "disk_percent": (
            f"max(100 * (1 - node_filesystem_avail_bytes{{{i},{_FS_FILTER}}} "
            f"/ node_filesystem_size_bytes{{{i},{_FS_FILTER}}}))"
        ),
        "input_mbps": (
            f"sum(rate(node_network_receive_bytes_total{{{i},{_NIC_FILTER}}}[5m])) * 8 / 1000000"
        ),
        "output_mbps": (
            f"sum(rate(node_network_transmit_bytes_total{{{i},{_NIC_FILTER}}}[5m])) * 8 / 1000000"
        ),
        "load_average_1m": f"node_load1{{{i}}}",
        "load_average_5m": f"node_load5{{{i}}}",
        "load_average_15m": f"node_load15{{{i}}}",
        "uptime_seconds": f"time() - node_boot_time_seconds{{{i}}}",
    }


@dataclass
class HostProbe:
    """Resultado de diagnóstico para un host del inventario."""

    external_id: str
    instance: str
    reachable: bool
    up_value: float | None
    metrics: dict[str, float | None] = field(default_factory=dict)
    error: str | None = None


def _clamp_percent(value: float) -> float:
    """Limita un porcentaje al rango [0, 100] (rate() puede exceder 100)."""
    return round(min(100.0, max(0.0, value)), 2)


class PrometheusInfrastructureAdapter(InfrastructureMetricsAdapter):
    """Adaptador de solo lectura sobre la API de consultas de Prometheus."""

    def __init__(
        self,
        base_url: str,
        inventory: Inventory,
        timeout_seconds: float = 10.0,
        bearer_token: str | None = None,
        verify_tls: bool = True,
        transport: httpx.BaseTransport | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._inventory = inventory
        self._timeout = timeout_seconds
        self._bearer_token = bearer_token
        self._verify_tls = verify_tls
        self._transport = transport
        self._now_fn = now_fn or (lambda: datetime.now(UTC))

    @property
    def source_name(self) -> str:
        """Identificador persistido junto a cada métrica."""
        return "prometheus"

    @property
    def verify_tls(self) -> bool:
        """Indica si la verificación TLS está activa (para diagnóstico)."""
        return self._verify_tls

    def _client(self) -> httpx.Client:
        """Cliente HTTP de solo lectura hacia la URL configurada."""
        headers = {}
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        return httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            verify=self._verify_tls,
            headers=headers,
            transport=self._transport,  # tests: transporte simulado
        )

    def _query_value(self, client: httpx.Client, promql: str) -> float | None:
        """Ejecuta una consulta instantánea y devuelve su valor escalar.

        Devuelve ``None`` si la consulta no produce series o el valor no
        es finito. Lanza ``PrometheusAuthError`` ante 401/403 y
        ``PrometheusSourceError`` ante respuestas malformadas o errores.
        """
        response = client.get(_QUERY_PATH, params={"query": promql})
        if response.status_code in (401, 403):
            # Nunca incluir cabeceras ni token en el mensaje.
            raise PrometheusAuthError(
                f"Prometheus rechazó las credenciales (HTTP {response.status_code})"
            )
        if response.status_code != 200:
            raise PrometheusSourceError(
                f"Prometheus respondió HTTP {response.status_code} a una consulta"
            )
        try:
            payload = response.json()
            if payload.get("status") != "success":
                raise PrometheusSourceError("Prometheus devolvió status != success")
            results = payload["data"]["result"]
            if not results:
                return None
            value = float(results[0]["value"][1])
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise PrometheusSourceError(
                f"Respuesta de Prometheus malformada: {type(error).__name__}"
            ) from error
        if not math.isfinite(value):
            return None
        return value

    def _collect_host(
        self, client: httpx.Client, server: InventoryServer, collected_at: datetime
    ) -> InfrastructureMetricSnapshot | None:
        """Consulta y normaliza las métricas de un host del inventario."""
        queries = build_queries(server.node_exporter_instance)
        up_value = self._query_value(client, queries.pop("up"))
        if up_value is not None and up_value < 1:
            logger.warning(
                "host reportado como caído por Prometheus (up=0) external_id=%s",
                server.external_id,
            )
            return None

        values: dict[str, float | None] = {
            name: self._query_value(client, promql) for name, promql in queries.items()
        }
        missing = [name for name in _ESSENTIAL_METRICS if values[name] is None]
        if missing:
            logger.warning(
                "host sin métricas esenciales (%s) external_id=%s: sin muestra",
                ",".join(missing),
                server.external_id,
            )
            return None

        def _optional(name: str, digits: int = 2) -> float | None:
            value = values[name]
            return round(max(0.0, value), digits) if value is not None else None

        disk = values["disk_percent"]
        uptime = values["uptime_seconds"]
        cpu = values["cpu_percent"]
        memory = values["memory_percent"]
        input_mbps = values["input_mbps"]
        output_mbps = values["output_mbps"]
        assert cpu is not None and memory is not None
        assert input_mbps is not None and output_mbps is not None
        return InfrastructureMetricSnapshot(
            server_external_id=server.external_id,
            collected_at=collected_at,
            cpu_percent=_clamp_percent(cpu),
            memory_percent=_clamp_percent(memory),
            disk_percent=_clamp_percent(disk) if disk is not None else None,
            input_mbps=round(max(0.0, input_mbps), 2),
            output_mbps=round(max(0.0, output_mbps), 2),
            load_average_1m=_optional("load_average_1m"),
            load_average_5m=_optional("load_average_5m"),
            load_average_15m=_optional("load_average_15m"),
            uptime_seconds=int(uptime) if uptime is not None and uptime >= 0 else None,
            status=ServerStatus.ONLINE if up_value is not None else ServerStatus.UNKNOWN,
        )

    def get_servers(self) -> list[ServerSnapshot]:
        """Inventario local de servidores (sin consultar la red)."""
        return [server.to_snapshot() for server in self._inventory.servers]

    def get_infrastructure_metrics(self) -> list[InfrastructureMetricSnapshot]:
        """Una muestra por host del inventario habilitado.

        Un host que falla se omite (con log); si fallan TODOS y hubo
        errores de consulta, se lanza ``PrometheusSourceError``.
        """
        collected_at = self._now_fn().replace(second=0, microsecond=0)
        snapshots: list[InfrastructureMetricSnapshot] = []
        failures: list[str] = []
        enabled = [server for server in self._inventory.servers if server.enabled]

        with self._client() as client:
            for server in enabled:
                try:
                    snapshot = self._collect_host(client, server, collected_at)
                except PrometheusAuthError:
                    raise  # credenciales inválidas: error de configuración global
                except (httpx.HTTPError, PrometheusSourceError) as error:
                    failures.append(f"{server.external_id}: {type(error).__name__}")
                    logger.warning(
                        "fallo consultando host external_id=%s: %s",
                        server.external_id,
                        type(error).__name__,
                    )
                    continue
                if snapshot is not None:
                    snapshots.append(snapshot)

        if enabled and not snapshots and failures:
            raise PrometheusSourceError(f"ningún host respondió; fallos: {'; '.join(failures)}")
        return snapshots

    def probe(self) -> list[HostProbe]:
        """Diagnóstico por host: qué métricas entrega cada consulta.

        No escribe en la base de datos; solo realiza las mismas
        solicitudes GET de una recolección normal.
        """
        probes: list[HostProbe] = []
        with self._client() as client:
            for server in self._inventory.servers:
                queries = build_queries(server.node_exporter_instance)
                probe = HostProbe(
                    external_id=server.external_id,
                    instance=server.node_exporter_instance,
                    reachable=True,
                    up_value=None,
                )
                try:
                    probe.up_value = self._query_value(client, queries.pop("up"))
                    for name, promql in queries.items():
                        probe.metrics[name] = self._query_value(client, promql)
                except PrometheusAuthError as error:
                    probe.reachable = False
                    probe.error = str(error)
                except (httpx.HTTPError, PrometheusSourceError) as error:
                    probe.reachable = False
                    probe.error = f"{type(error).__name__}: {error}"
                probes.append(probe)
        return probes
