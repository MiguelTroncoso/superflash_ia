"""Adaptadores mock de demostración para los contratos por tipo de fuente.

Ambos envuelven ``MockMonitoringAdapter`` con la misma semilla, de modo
que la "infraestructura simulada" y el "panel de streaming simulado"
describen exactamente el mismo mundo (mismos servidores, mismos canales,
misma muestra por minuto) sin duplicar la lógica de simulación ni alterar
el comportamiento del mock original.
"""

import random
from collections.abc import Callable
from datetime import datetime

from app.adapters.base import ChannelSnapshot, ServerSnapshot
from app.adapters.mock import MockMonitoringAdapter
from app.adapters.sources import (
    InfrastructureMetricsAdapter,
    InfrastructureMetricSnapshot,
    ServerStatus,
    StreamingChannelMetricSnapshot,
    StreamingMetricsAdapter,
)
from app.models.channel import ChannelStatus

# Por encima de este umbral de CPU el mock reporta el servidor degradado.
_DEGRADED_CPU_THRESHOLD = 92.0


class MockInfrastructureAdapter(InfrastructureMetricsAdapter):
    """Fuente simulada de métricas de máquina (CPU, RAM, disco, carga, red)."""

    def __init__(self, seed: int = 42, now_fn: Callable[[], datetime] | None = None) -> None:
        self._seed = seed
        self._inner = MockMonitoringAdapter(seed=seed, now_fn=now_fn)

    @property
    def source_name(self) -> str:
        """Identificador de la fuente simulada de infraestructura."""
        return "mock-infra"

    def get_servers(self) -> list[ServerSnapshot]:
        """Inventario simulado de servidores (idéntico al mock combinado)."""
        return self._inner.get_servers()

    def get_infrastructure_metrics(self) -> list[InfrastructureMetricSnapshot]:
        """Muestra de máquina derivada del mock, ampliada con disco y carga.

        Disco y load average no existen en el mock combinado; se generan
        de forma determinista por (semilla, minuto, servidor) para que la
        muestra siga siendo reproducible.
        """
        snapshots: list[InfrastructureMetricSnapshot] = []
        for metric in self._inner.get_server_metrics():
            rng = random.Random(
                f"mock-infra:{self._seed}:{metric.collected_at.isoformat()}:"
                f"{metric.server_external_id}"
            )
            load_base = metric.cpu_percent / 100 * 8  # ~8 núcleos simulados
            snapshots.append(
                InfrastructureMetricSnapshot(
                    server_external_id=metric.server_external_id,
                    collected_at=metric.collected_at,
                    cpu_percent=metric.cpu_percent,
                    memory_percent=metric.memory_percent,
                    disk_percent=round(rng.uniform(35.0, 85.0), 2),
                    filesystem_percent=round(rng.uniform(35.0, 85.0), 2),
                    swap_percent=round(rng.uniform(5.0, 35.0), 2),
                    input_mbps=metric.input_mbps,
                    output_mbps=metric.output_mbps,
                    io_read_mbps=round(rng.uniform(20.0, 120.0), 2),
                    io_write_mbps=round(rng.uniform(10.0, 80.0), 2),
                    load_average_1m=round(load_base * rng.uniform(0.9, 1.1), 2),
                    load_average_5m=round(load_base * rng.uniform(0.8, 1.0), 2),
                    load_average_15m=round(load_base * rng.uniform(0.7, 0.9), 2),
                    uptime_seconds=metric.uptime_seconds,
                    status=(
                        ServerStatus.DEGRADED
                        if metric.cpu_percent > _DEGRADED_CPU_THRESHOLD
                        else ServerStatus.ONLINE
                    ),
                )
            )
        return snapshots


class MockStreamingAdapter(StreamingMetricsAdapter):
    """Fuente simulada de métricas de audiencia por canal."""

    def __init__(self, seed: int = 42, now_fn: Callable[[], datetime] | None = None) -> None:
        self._inner = MockMonitoringAdapter(seed=seed, now_fn=now_fn)

    @property
    def source_name(self) -> str:
        """Identificador de la fuente simulada de streaming."""
        return "mock-streaming"

    def get_channels(self) -> list[ChannelSnapshot]:
        """Inventario simulado de canales (idéntico al mock combinado)."""
        return self._inner.get_channels()

    def get_streaming_metrics(self) -> list[StreamingChannelMetricSnapshot]:
        """Muestra de audiencia derivada del mock combinado."""
        return [
            StreamingChannelMetricSnapshot(
                channel_external_id=metric.channel_external_id,
                source_id=metric.source_id,
                server_external_id=metric.server_external_id,
                event_external_id=metric.event_external_id,
                technical_stream_external_id=metric.technical_stream_external_id,
                collected_at=metric.collected_at,
                viewers=metric.viewers,
                bitrate_mbps=metric.bitrate_mbps,
                status=metric.status if metric.status is not None else ChannelStatus.UNKNOWN,
            )
            for metric in self._inner.get_channel_metrics()
        ]
