"""Cálculo del resumen agregado de la infraestructura."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.repositories.channel_repository import ChannelRepository
from app.repositories.server_repository import ServerRepository
from app.schemas.overview import (
    OverviewRead,
    ServerUtilization,
    TopChannel,
    TopOutputServer,
)

TOP_CHANNELS_LIMIT = 5


def compute_network_utilization(
    output_mbps: float, network_capacity_mbps: float | None
) -> float | None:
    """Porcentaje de utilización de red: ``output / capacidad * 100``.

    Devuelve ``None`` cuando la capacidad es desconocida (``None``) o no
    positiva, ya que el cálculo no tiene sentido en esos casos.
    """
    if network_capacity_mbps is None or network_capacity_mbps <= 0:
        return None
    return round(output_mbps / network_capacity_mbps * 100, 2)


class OverviewService:
    """Construye el resumen global a partir de las últimas muestras."""

    def __init__(self, session: Session) -> None:
        self._servers = ServerRepository(session)
        self._channels = ChannelRepository(session)

    def build(self) -> OverviewRead:
        """Agrega las métricas más recientes de servidores y canales."""
        latest = self._servers.latest_metrics_for_enabled()

        total_connections = sum(metric.active_connections for _, metric in latest)
        total_output = round(sum(metric.output_mbps for _, metric in latest), 2)
        total_input = round(sum(metric.input_mbps for _, metric in latest), 2)
        avg_cpu = (
            round(sum(metric.cpu_percent for _, metric in latest) / len(latest), 2)
            if latest
            else None
        )
        avg_memory = (
            round(sum(metric.memory_percent for _, metric in latest) / len(latest), 2)
            if latest
            else None
        )

        top_output: TopOutputServer | None = None
        if latest:
            server, metric = max(latest, key=lambda pair: pair[1].output_mbps)
            top_output = TopOutputServer(
                server_id=server.id, name=server.name, output_mbps=metric.output_mbps
            )

        utilization = [
            ServerUtilization(
                server_id=server.id,
                name=server.name,
                output_mbps=metric.output_mbps,
                network_capacity_mbps=server.network_capacity_mbps,
                utilization_percent=compute_network_utilization(
                    metric.output_mbps, server.network_capacity_mbps
                ),
            )
            for server, metric in latest
        ]

        top_channels = [
            TopChannel(
                channel_id=channel.id,
                name=channel.name,
                viewers=metric.viewers,
                collected_at=metric.collected_at,
            )
            for channel, metric in self._channels.top_channels_by_latest_viewers(TOP_CHANNELS_LIMIT)
        ]

        return OverviewRead(
            generated_at=datetime.now(UTC),
            enabled_servers=self._servers.count_enabled(),
            total_active_connections=total_connections,
            total_output_mbps=total_output,
            total_input_mbps=total_input,
            avg_cpu_percent=avg_cpu,
            avg_memory_percent=avg_memory,
            top_output_server=top_output,
            server_network_utilization=utilization,
            top_channels=top_channels,
        )
