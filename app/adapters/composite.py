"""Puente entre las fuentes por tipo y el pipeline de persistencia actual.

``CompositeMonitoringAdapter`` combina una fuente de infraestructura y
una de streaming en el contrato histórico ``MonitoringSourceAdapter``,
de modo que ``CollectionService`` funciona sin cambios sea cual sea el
origen de los datos.

Cada pasada de recolección consulta cada fuente **una sola vez**: la
muestra completa se captura en un ``CompositeCycleSnapshot`` inmutable
al primer acceso del ciclo y se reutiliza para servidores y canales, lo
que garantiza consistencia temporal dentro de la pasada.
``begin_collection_cycle()`` (invocado por ``CollectionService`` al
inicio de cada pasada) invalida la muestra anterior.

El esquema de base de datos solo persiste, de los campos nuevos,
``disk_percent``; el resto (load average, estado del servidor) vive en
los snapshots hasta que una fuente real confirme qué entrega.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.adapters.base import (
    ChannelMetricSnapshot,
    ChannelSnapshot,
    MonitoringSourceAdapter,
    ServerMetricSnapshot,
    ServerSnapshot,
)
from app.adapters.sources import (
    InfrastructureMetricsAdapter,
    InfrastructureMetricSnapshot,
    StreamingChannelMetricSnapshot,
    StreamingMetricsAdapter,
)


@dataclass(frozen=True)
class CompositeCycleSnapshot:
    """Muestra completa de ambas fuentes, capturada una vez por ciclo."""

    fetched_at: datetime
    servers: tuple[ServerSnapshot, ...]
    channels: tuple[ChannelSnapshot, ...]
    infrastructure_metrics: tuple[InfrastructureMetricSnapshot, ...]
    streaming_metrics: tuple[StreamingChannelMetricSnapshot, ...]


class CompositeMonitoringAdapter(MonitoringSourceAdapter):
    """Une infraestructura + streaming hacia el contrato de recolección."""

    def __init__(
        self,
        infrastructure: InfrastructureMetricsAdapter,
        streaming: StreamingMetricsAdapter,
    ) -> None:
        self._infrastructure = infrastructure
        self._streaming = streaming
        self._cycle: CompositeCycleSnapshot | None = None

    @property
    def source_name(self) -> str:
        """Nombre compuesto; se persiste en ``ServerMetric.source``."""
        return f"{self._infrastructure.source_name}+{self._streaming.source_name}"

    def begin_collection_cycle(self) -> None:
        """Descarta la muestra del ciclo anterior; la próxima lectura refresca."""
        self._cycle = None

    def _snapshot(self) -> CompositeCycleSnapshot:
        """Captura (una sola vez por ciclo) la muestra de ambas fuentes."""
        if self._cycle is None:
            self._cycle = CompositeCycleSnapshot(
                fetched_at=datetime.now(UTC),
                servers=tuple(self._infrastructure.get_servers()),
                channels=tuple(self._streaming.get_channels()),
                infrastructure_metrics=tuple(self._infrastructure.get_infrastructure_metrics()),
                streaming_metrics=tuple(self._streaming.get_streaming_metrics()),
            )
        return self._cycle

    def get_servers(self) -> list[ServerSnapshot]:
        """Inventario de servidores de la muestra del ciclo."""
        return list(self._snapshot().servers)

    def get_channels(self) -> list[ChannelSnapshot]:
        """Inventario de canales de la muestra del ciclo."""
        return list(self._snapshot().channels)

    def get_server_metrics(self) -> list[ServerMetricSnapshot]:
        """Métricas de máquina + agregados de audiencia por servidor.

        La fuente de infraestructura no conoce conexiones ni streams; se
        derivan de la muestra de streaming del mismo ciclo: conexiones =
        suma de espectadores de los canales del servidor, streams =
        canales no offline alojados en él.
        """
        snapshot = self._snapshot()
        viewers_by_server: dict[str, int] = {}
        streams_by_server: dict[str, int] = {}
        for channel_metric in snapshot.streaming_metrics:
            server_key = channel_metric.server_external_id
            if server_key is None:
                continue
            viewers_by_server[server_key] = (
                viewers_by_server.get(server_key, 0) + channel_metric.viewers
            )
            if channel_metric.status.value != "offline":
                streams_by_server[server_key] = streams_by_server.get(server_key, 0) + 1

        return [
            ServerMetricSnapshot(
                server_external_id=metric.server_external_id,
                collected_at=metric.collected_at,
                cpu_percent=metric.cpu_percent,
                memory_percent=metric.memory_percent,
                disk_percent=metric.disk_percent,
                filesystem_percent=metric.filesystem_percent,
                swap_percent=metric.swap_percent,
                input_mbps=metric.input_mbps,
                output_mbps=metric.output_mbps,
                io_read_mbps=metric.io_read_mbps,
                io_write_mbps=metric.io_write_mbps,
                load_average_1m=metric.load_average_1m,
                load_average_5m=metric.load_average_5m,
                load_average_15m=metric.load_average_15m,
                active_connections=viewers_by_server.get(metric.server_external_id, 0),
                active_streams=streams_by_server.get(metric.server_external_id, 0),
                uptime_seconds=metric.uptime_seconds,
            )
            for metric in snapshot.infrastructure_metrics
        ]

    def get_channel_metrics(self) -> list[ChannelMetricSnapshot]:
        """Métricas de canal; el output estimado se deriva de viewers*bitrate."""
        return [
            ChannelMetricSnapshot(
                channel_external_id=metric.channel_external_id,
                server_external_id=metric.server_external_id,
                collected_at=metric.collected_at,
                viewers=metric.viewers,
                bitrate_mbps=metric.bitrate_mbps,
                estimated_output_mbps=(
                    round(metric.viewers * metric.bitrate_mbps, 2)
                    if metric.bitrate_mbps is not None
                    else None
                ),
                status=metric.status,
            )
            for metric in self._snapshot().streaming_metrics
        ]
