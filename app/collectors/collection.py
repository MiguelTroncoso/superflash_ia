"""Servicio de recolección de métricas.

Orquesta una pasada completa: sincroniza inventario (servidores y
canales por ``external_id``) y persiste una muestra de métricas. Un
fallo en un servidor o canal individual se registra y NO aborta el resto
de la recolección (cada elemento se procesa dentro de un savepoint).

La arquitectura está preparada para que, en una fase futura, un
programador (p. ej. cron o un scheduler in-process) invoque
``CollectionService.run()`` cada cinco minutos.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.adapters.base import MonitoringSourceAdapter
from app.models.channel import ChannelMetric
from app.models.server import ServerMetric
from app.repositories.channel_repository import ChannelRepository
from app.repositories.server_repository import ServerRepository
from app.schemas.collection import CollectionResult

logger = logging.getLogger(__name__)


class CollectionService:
    """Ejecuta una recolección completa contra el adaptador configurado."""

    def __init__(self, session: Session, adapter: MonitoringSourceAdapter) -> None:
        self._session = session
        self._adapter = adapter
        self._servers = ServerRepository(session)
        self._channels = ChannelRepository(session)

    def run(self) -> CollectionResult:
        """Sincroniza inventario, guarda métricas y devuelve un resumen.

        La operación completa se confirma con un único ``commit`` final;
        los fallos por elemento se aíslan con savepoints para no perder
        el resto de la muestra.
        """
        result = CollectionResult(adapter=self._adapter.source_name, collected_at=datetime.now(UTC))

        server_ids = self._sync_servers(result)
        self._sync_channels(result, server_ids)
        self._store_server_metrics(result, server_ids)
        self._store_channel_metrics(result, server_ids)

        self._session.commit()
        logger.info(
            "recoleccion terminada adapter=%s servers=%d channels=%d "
            "server_metrics=%d channel_metrics=%d errores=%d",
            result.adapter,
            result.servers_synced,
            result.channels_synced,
            result.server_metrics_inserted,
            result.channel_metrics_inserted,
            len(result.errors),
        )
        return result

    def _record_error(self, result: CollectionResult, message: str, exc: Exception) -> None:
        """Registra un error no fatal y lo añade al resumen."""
        logger.exception("%s", message)
        result.errors.append(f"{message}: {exc.__class__.__name__}")

    def _sync_servers(self, result: CollectionResult) -> dict[str, int]:
        """Crea/actualiza servidores; devuelve mapa external_id -> id."""
        server_ids: dict[str, int] = {}
        for snapshot in self._adapter.get_servers():
            try:
                with self._session.begin_nested():
                    server = self._servers.upsert_from_snapshot(snapshot)
                server_ids[snapshot.external_id] = server.id
                result.servers_synced += 1
            except Exception as exc:  # aislamiento por elemento
                self._record_error(
                    result, f"fallo sincronizando servidor {snapshot.external_id}", exc
                )
        return server_ids

    def _sync_channels(self, result: CollectionResult, server_ids: dict[str, int]) -> None:
        """Crea/actualiza canales resolviendo su servidor actual."""
        for snapshot in self._adapter.get_channels():
            try:
                current_server_id = (
                    server_ids.get(snapshot.server_external_id)
                    if snapshot.server_external_id
                    else None
                )
                with self._session.begin_nested():
                    self._channels.upsert_from_snapshot(snapshot, current_server_id)
                result.channels_synced += 1
            except Exception as exc:  # aislamiento por elemento
                self._record_error(result, f"fallo sincronizando canal {snapshot.external_id}", exc)

    def _store_server_metrics(self, result: CollectionResult, server_ids: dict[str, int]) -> None:
        """Guarda la muestra de métricas de servidores, evitando duplicados."""
        for metric in self._adapter.get_server_metrics():
            server_id = server_ids.get(metric.server_external_id)
            if server_id is None:
                result.errors.append(
                    f"métrica de servidor desconocido: {metric.server_external_id}"
                )
                logger.warning(
                    "metrica descartada: servidor desconocido external_id=%s",
                    metric.server_external_id,
                )
                continue
            try:
                if self._servers.metric_exists(server_id, metric.collected_at):
                    result.server_metrics_skipped += 1
                    continue
                with self._session.begin_nested():
                    self._servers.add_metric(
                        ServerMetric(
                            server_id=server_id,
                            collected_at=metric.collected_at,
                            cpu_percent=metric.cpu_percent,
                            memory_percent=metric.memory_percent,
                            input_mbps=metric.input_mbps,
                            output_mbps=metric.output_mbps,
                            active_connections=metric.active_connections,
                            active_streams=metric.active_streams,
                            uptime_seconds=metric.uptime_seconds,
                            source=self._adapter.source_name,
                        )
                    )
                result.server_metrics_inserted += 1
            except Exception as exc:  # aislamiento por elemento
                self._record_error(
                    result, f"fallo guardando métrica de servidor {metric.server_external_id}", exc
                )

    def _store_channel_metrics(self, result: CollectionResult, server_ids: dict[str, int]) -> None:
        """Guarda la muestra de métricas de canales, evitando duplicados."""
        for metric in self._adapter.get_channel_metrics():
            channel = self._channels.get_by_external_id(metric.channel_external_id)
            if channel is None:
                result.errors.append(f"métrica de canal desconocido: {metric.channel_external_id}")
                logger.warning(
                    "metrica descartada: canal desconocido external_id=%s",
                    metric.channel_external_id,
                )
                continue
            try:
                if self._channels.metric_exists(channel.id, metric.collected_at):
                    result.channel_metrics_skipped += 1
                    continue
                server_id = (
                    server_ids.get(metric.server_external_id) if metric.server_external_id else None
                )
                with self._session.begin_nested():
                    self._channels.add_metric(
                        ChannelMetric(
                            channel_id=channel.id,
                            server_id=server_id,
                            collected_at=metric.collected_at,
                            viewers=metric.viewers,
                            bitrate_mbps=metric.bitrate_mbps,
                            estimated_output_mbps=metric.estimated_output_mbps,
                            status=metric.status,
                        )
                    )
                result.channel_metrics_inserted += 1
            except Exception as exc:  # aislamiento por elemento
                self._record_error(
                    result, f"fallo guardando métrica de canal {metric.channel_external_id}", exc
                )
