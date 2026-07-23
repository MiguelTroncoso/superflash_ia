"""Adaptador de monitoreo con datos simulados, reproducibles por semilla.

Genera una infraestructura coherente: los espectadores de cada canal
determinan el tráfico de salida del servidor que lo aloja, y la carga de
CPU/memoria crece con la utilización de red. La misma semilla y el mismo
minuto de recolección producen exactamente la misma muestra.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.adapters.base import (
    ChannelMetricSnapshot,
    ChannelSnapshot,
    MonitoringSourceAdapter,
    ServerMetricSnapshot,
    ServerSnapshot,
)
from app.models.channel import ChannelStatus
from app.models.server import ServerRole


@dataclass(frozen=True)
class _ServerSpec:
    external_id: str
    name: str
    hostname: str
    role: ServerRole
    network_capacity_mbps: float


@dataclass(frozen=True)
class _ChannelSpec:
    external_id: str
    name: str
    category: str
    server_external_id: str
    base_viewers: int
    bitrate_mbps: float


_SERVER_SPECS: tuple[_ServerSpec, ...] = (
    _ServerSpec("srv-main-01", "Main 01", "main01.example.internal", ServerRole.MAIN, 20000.0),
    _ServerSpec("srv-live-01", "Live 01", "live01.example.internal", ServerRole.LIVE, 10000.0),
    _ServerSpec("srv-live-02", "Live 02", "live02.example.internal", ServerRole.LIVE, 10000.0),
    _ServerSpec("srv-vod-01", "VOD 01", "vod01.example.internal", ServerRole.VOD, 5000.0),
    _ServerSpec("srv-edge-01", "Edge 01", "edge01.example.internal", ServerRole.OTHER, 1000.0),
)

# (nombre, categoría, servidor, nivel de popularidad 0=alto .. 3=bajo)
_CHANNEL_SEEDS: tuple[tuple[str, str, str, int], ...] = (
    ("Deportes Uno", "deportes", "srv-live-01", 0),
    ("Deportes Dos", "deportes", "srv-live-01", 1),
    ("Fútbol Total", "deportes", "srv-live-02", 0),
    ("Motor Extremo", "deportes", "srv-live-02", 2),
    ("Noticias 24", "noticias", "srv-live-01", 1),
    ("Noticias Mundo", "noticias", "srv-live-02", 1),
    ("Economía Hoy", "noticias", "srv-main-01", 2),
    ("Clima Ya", "noticias", "srv-main-01", 3),
    ("Cine Premium", "cine", "srv-live-01", 1),
    ("Cine Clásico", "cine", "srv-vod-01", 2),
    ("Cine Acción", "cine", "srv-live-02", 1),
    ("Cine Familiar", "cine", "srv-vod-01", 2),
    ("Series Plus", "cine", "srv-vod-01", 1),
    ("Infantil Uno", "infantil", "srv-live-01", 2),
    ("Dibujos TV", "infantil", "srv-live-02", 2),
    ("Peques Club", "infantil", "srv-vod-01", 3),
    ("Música Top", "musica", "srv-live-01", 2),
    ("Rock Nacional", "musica", "srv-live-02", 3),
    ("Clásica FM", "musica", "srv-main-01", 3),
    ("Documental Mundo", "documentales", "srv-main-01", 2),
    ("Naturaleza Viva", "documentales", "srv-live-01", 3),
    ("Historia Canal", "documentales", "srv-live-02", 3),
    ("Cocina Gourmet", "estilo", "srv-live-01", 3),
    ("Viajes 360", "estilo", "srv-live-02", 3),
)

# Rangos de espectadores base por nivel de popularidad.
_VIEWER_TIERS: tuple[tuple[int, int], ...] = ((800, 1500), (300, 800), (100, 300), (10, 100))


@dataclass(frozen=True)
class _Snapshot:
    servers: tuple[ServerMetricSnapshot, ...]
    channels: tuple[ChannelMetricSnapshot, ...]


class MockMonitoringAdapter(MonitoringSourceAdapter):
    """Fuente simulada de monitoreo (única implementación en esta fase)."""

    def __init__(self, seed: int = 42, now_fn: Callable[[], datetime] | None = None) -> None:
        """Inicializa el adaptador.

        Args:
            seed: Semilla del generador; misma semilla = misma simulación.
            now_fn: Reloj inyectable (para tests). Por defecto, hora UTC real.
        """
        self._seed = seed
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._channel_specs = self._build_channel_specs(seed)
        self._cache: tuple[datetime, _Snapshot] | None = None

    @property
    def source_name(self) -> str:
        """Identificador persistido junto a cada métrica."""
        return "mock"

    @staticmethod
    def _build_channel_specs(seed: int) -> tuple[_ChannelSpec, ...]:
        """Fija atributos estables de cada canal a partir de la semilla."""
        rng = random.Random(f"mock-channels:{seed}")
        specs: list[_ChannelSpec] = []
        for index, (name, category, server_external_id, tier) in enumerate(_CHANNEL_SEEDS, 1):
            low, high = _VIEWER_TIERS[tier]
            specs.append(
                _ChannelSpec(
                    external_id=f"ch-{index:03d}",
                    name=name,
                    category=category,
                    server_external_id=server_external_id,
                    base_viewers=rng.randint(low, high),
                    bitrate_mbps=rng.choice((2.0, 3.0, 4.0, 6.0)),
                )
            )
        return tuple(specs)

    def _collection_timestamp(self) -> datetime:
        """Hora de la muestra, truncada al minuto (ventana de muestreo)."""
        return self._now_fn().replace(second=0, microsecond=0)

    def _snapshot(self) -> _Snapshot:
        """Genera (o reutiliza) la muestra completa del minuto actual.

        Calcular canales y servidores en un solo paso mantiene la
        coherencia: el output de un servidor es la suma del output
        estimado de sus canales.
        """
        collected_at = self._collection_timestamp()
        if self._cache is not None and self._cache[0] == collected_at:
            return self._cache[1]

        rng = random.Random(f"mock-sample:{self._seed}:{collected_at.isoformat()}")

        channel_metrics: list[ChannelMetricSnapshot] = []
        per_server_output: dict[str, float] = {spec.external_id: 0.0 for spec in _SERVER_SPECS}
        per_server_input: dict[str, float] = dict(per_server_output)
        per_server_viewers: dict[str, int] = dict.fromkeys(per_server_output, 0)
        per_server_streams: dict[str, int] = dict.fromkeys(per_server_output, 0)

        for spec in self._channel_specs:
            roll = rng.random()
            if roll < 0.02:
                status, factor = ChannelStatus.OFFLINE, 0.0
            elif roll < 0.07:
                status, factor = ChannelStatus.DEGRADED, rng.uniform(0.2, 0.5)
            else:
                status, factor = ChannelStatus.ONLINE, rng.uniform(0.7, 1.3)

            viewers = int(spec.base_viewers * factor)
            estimated_output = round(viewers * spec.bitrate_mbps, 2)
            channel_metrics.append(
                ChannelMetricSnapshot(
                    channel_external_id=spec.external_id,
                    server_external_id=spec.server_external_id,
                    collected_at=collected_at,
                    viewers=viewers,
                    bitrate_mbps=spec.bitrate_mbps,
                    estimated_output_mbps=estimated_output,
                    status=status,
                )
            )
            per_server_output[spec.server_external_id] += estimated_output
            per_server_input[spec.server_external_id] += spec.bitrate_mbps
            per_server_viewers[spec.server_external_id] += viewers
            if status is not ChannelStatus.OFFLINE:
                per_server_streams[spec.server_external_id] += 1

        server_metrics: list[ServerMetricSnapshot] = []
        for server in _SERVER_SPECS:
            output = per_server_output[server.external_id]
            if output == 0.0:
                # Servidores sin canales (p. ej. edge) mantienen tráfico residual.
                output = round(rng.uniform(0.02, 0.15) * server.network_capacity_mbps, 2)
            output = min(output, server.network_capacity_mbps * 0.97)
            load = output / server.network_capacity_mbps
            server_metrics.append(
                ServerMetricSnapshot(
                    server_external_id=server.external_id,
                    collected_at=collected_at,
                    cpu_percent=round(min(99.0, 8.0 + load * 75.0 + rng.uniform(0.0, 8.0)), 2),
                    memory_percent=round(min(97.0, 22.0 + load * 45.0 + rng.uniform(0.0, 10.0)), 2),
                    input_mbps=round(
                        per_server_input[server.external_id] + rng.uniform(1.0, 20.0), 2
                    ),
                    output_mbps=round(output, 2),
                    active_connections=per_server_viewers[server.external_id] + rng.randint(0, 50),
                    active_streams=per_server_streams[server.external_id],
                    uptime_seconds=rng.randint(3_600 * 24, 3_600 * 24 * 200),
                )
            )

        snapshot = _Snapshot(servers=tuple(server_metrics), channels=tuple(channel_metrics))
        self._cache = (collected_at, snapshot)
        return snapshot

    def get_servers(self) -> list[ServerSnapshot]:
        """Inventario simulado de servidores (al menos cuatro)."""
        return [
            ServerSnapshot(
                external_id=spec.external_id,
                name=spec.name,
                hostname=spec.hostname,
                role=spec.role,
                network_capacity_mbps=spec.network_capacity_mbps,
                enabled=True,
            )
            for spec in _SERVER_SPECS
        ]

    def get_server_metrics(self) -> list[ServerMetricSnapshot]:
        """Muestra de métricas por servidor del minuto actual."""
        return list(self._snapshot().servers)

    def get_channels(self) -> list[ChannelSnapshot]:
        """Inventario simulado de canales (al menos veinte)."""
        return [
            ChannelSnapshot(
                external_id=spec.external_id,
                name=spec.name,
                category=spec.category,
                server_external_id=spec.server_external_id,
                enabled=True,
            )
            for spec in self._channel_specs
        ]

    def get_channel_metrics(self) -> list[ChannelMetricSnapshot]:
        """Muestra de métricas por canal del minuto actual."""
        return list(self._snapshot().channels)
