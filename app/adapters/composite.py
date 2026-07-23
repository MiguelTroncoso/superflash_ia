"""Puente entre las fuentes por tipo y el pipeline de persistencia actual.

``CompositeMonitoringAdapter`` combina una fuente de infraestructura y
una de streaming en el contrato histórico ``MonitoringSourceAdapter``,
de modo que ``CollectionService`` funciona sin cambios sea cual sea el
origen de los datos. El esquema de base de datos no cambia: los campos
nuevos de los snapshots (disco, load average, estado del servidor) aún
no se persisten; se incorporarán con una migración cuando una fuente
real confirme qué entrega.
"""

from app.adapters.base import (
    ChannelMetricSnapshot,
    ChannelSnapshot,
    MonitoringSourceAdapter,
    ServerMetricSnapshot,
    ServerSnapshot,
)
from app.adapters.sources import InfrastructureMetricsAdapter, StreamingMetricsAdapter


class CompositeMonitoringAdapter(MonitoringSourceAdapter):
    """Une infraestructura + streaming hacia el contrato de recolección."""

    def __init__(
        self,
        infrastructure: InfrastructureMetricsAdapter,
        streaming: StreamingMetricsAdapter,
    ) -> None:
        self._infrastructure = infrastructure
        self._streaming = streaming

    @property
    def source_name(self) -> str:
        """Nombre compuesto; se persiste en ``ServerMetric.source``."""
        return f"{self._infrastructure.source_name}+{self._streaming.source_name}"

    def get_servers(self) -> list[ServerSnapshot]:
        """El inventario de servidores proviene de la fuente de infraestructura."""
        return self._infrastructure.get_servers()

    def get_channels(self) -> list[ChannelSnapshot]:
        """El inventario de canales proviene de la fuente de streaming."""
        return self._streaming.get_channels()

    def get_server_metrics(self) -> list[ServerMetricSnapshot]:
        """Métricas de máquina + agregados de audiencia por servidor.

        La fuente de infraestructura no conoce conexiones ni streams;
        se derivan de la muestra de streaming: conexiones = suma de
        espectadores de los canales del servidor, streams = canales no
        offline alojados en él.
        """
        viewers_by_server: dict[str, int] = {}
        streams_by_server: dict[str, int] = {}
        for channel_metric in self._streaming.get_streaming_metrics():
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
                input_mbps=metric.input_mbps,
                output_mbps=metric.output_mbps,
                active_connections=viewers_by_server.get(metric.server_external_id, 0),
                active_streams=streams_by_server.get(metric.server_external_id, 0),
                uptime_seconds=metric.uptime_seconds,
            )
            for metric in self._infrastructure.get_infrastructure_metrics()
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
            for metric in self._streaming.get_streaming_metrics()
        ]
