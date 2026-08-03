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
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.adapters.base import MonitoringSourceAdapter
from app.models.channel import ChannelMetric
from app.models.server import ServerMetric, ServerOperationalStatus
from app.repositories.channel_repository import ChannelRepository
from app.repositories.server_repository import ServerRepository
from app.schemas.collection import CollectionResult

logger = logging.getLogger(__name__)


class CollectionService:
    """Ejecuta una recolección completa contra el adaptador configurado."""

    def __init__(
        self,
        session: Session,
        adapter: MonitoringSourceAdapter,
        on_heartbeat: Callable[[], None] | None = None,
        event_inactive_grace_hours: int = 6,
        event_archive_days: int = 7,
        permanent_archive_days: int = 30,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._adapter = adapter
        self._on_heartbeat = on_heartbeat
        self._event_inactive_grace_hours = event_inactive_grace_hours
        self._event_archive_days = event_archive_days
        self._permanent_archive_days = permanent_archive_days
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._servers = ServerRepository(session)
        self._channels = ChannelRepository(session)

    def _heartbeat(self) -> None:
        """Señal de vida entre fases (el runner la persiste)."""
        if self._on_heartbeat is not None:
            self._on_heartbeat()

    def run(self) -> CollectionResult:
        """Sincroniza inventario, guarda métricas y devuelve un resumen.

        La operación completa se confirma con un único ``commit`` final;
        los fallos por elemento se aíslan con savepoints para no perder
        el resto de la muestra.
        """
        result = CollectionResult(adapter=self._adapter.source_name, collected_at=self._now_fn())

        # Un ciclo nuevo: los adaptadores que cachean su muestra la refrescan
        # aquí y la reutilizan en las cuatro lecturas de esta pasada.
        self._adapter.begin_collection_cycle()

        server_ids = self._sync_servers(result)
        self._heartbeat()
        self._sync_channels(result, server_ids)
        self._heartbeat()
        self._store_server_metrics(result, server_ids)
        self._heartbeat()
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
        """Sincroniza altas/cambios y reconcilia ausencias por fuente."""
        snapshots = self._adapter.get_channels()
        seen_by_source: dict[str, set[str]] = defaultdict(set)
        seen_by_source.setdefault(self._adapter.source_name, set())
        for snapshot in snapshots:
            source_id = snapshot.source_id or self._adapter.source_name
            seen_by_source[source_id].add(snapshot.external_id)
            try:
                current_server_id = (
                    server_ids.get(snapshot.server_external_id)
                    if snapshot.server_external_id
                    else None
                )
                with self._session.begin_nested():
                    outcome = self._channels.upsert_from_snapshot(
                        snapshot,
                        current_server_id,
                        source_id=source_id,
                        seen_at=result.collected_at,
                    )
                result.channels_synced += 1
                counter_name = f"channels_{outcome.action}"
                setattr(result, counter_name, getattr(result, counter_name) + 1)
            except Exception as exc:  # aislamiento por elemento
                result.channels_failed += 1
                self._record_error(result, f"fallo sincronizando canal {snapshot.external_id}", exc)

        for source_id, seen_external_ids in seen_by_source.items():
            try:
                with self._session.begin_nested():
                    reconciliation = self._channels.reconcile_missing(
                        source_id=source_id,
                        seen_external_ids=seen_external_ids,
                        observed_at=result.collected_at,
                        event_inactive_grace_hours=self._event_inactive_grace_hours,
                        event_archive_days=self._event_archive_days,
                        permanent_archive_days=self._permanent_archive_days,
                    )
                result.channels_deactivated += reconciliation.deactivated
                result.channels_archived += reconciliation.archived
            except Exception as exc:
                result.channels_failed += 1
                self._record_error(result, f"fallo reconciliando fuente {source_id}", exc)

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
                            active_connections=metric.active_connections,
                            active_streams=metric.active_streams,
                            uptime_seconds=metric.uptime_seconds,
                            source=self._adapter.source_name,
                        )
                    )
                    server = self._servers.get(server_id)
                    if server is not None:
                        server.last_heartbeat_at = metric.collected_at
                        if server.status is not ServerOperationalStatus.MAINTENANCE:
                            server.status = ServerOperationalStatus.ONLINE
                result.server_metrics_inserted += 1
            except Exception as exc:  # aislamiento por elemento
                self._record_error(
                    result, f"fallo guardando métrica de servidor {metric.server_external_id}", exc
                )

    def _store_channel_metrics(self, result: CollectionResult, server_ids: dict[str, int]) -> None:
        """Guarda métricas de canales con resolución batched de identidades."""
        metrics = self._adapter.get_channel_metrics()
        default_source = self._adapter.source_name
        channel_identities = {
            (metric.source_id or default_source, metric.channel_external_id) for metric in metrics
        }
        channels = self._channels.get_by_identities(channel_identities)
        event_identities = {
            (metric.source_id or default_source, metric.event_external_id)
            for metric in metrics
            if metric.event_external_id is not None
        }
        stream_identities = {
            (metric.source_id or default_source, metric.technical_stream_external_id)
            for metric in metrics
            if metric.technical_stream_external_id is not None
        }
        events = self._channels.get_events_by_identities(event_identities)
        streams = self._channels.get_streams_by_identities(stream_identities)

        for metric in metrics:
            source_id = metric.source_id or default_source
            channel = channels.get((source_id, metric.channel_external_id))
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
                event = (
                    events.get((source_id, metric.event_external_id))
                    if metric.event_external_id is not None
                    else None
                )
                stream = (
                    streams.get((source_id, metric.technical_stream_external_id))
                    if metric.technical_stream_external_id is not None
                    else None
                )
                with self._session.begin_nested():
                    self._channels.add_metric(
                        ChannelMetric(
                            channel_id=channel.id,
                            event_id=event.id if event is not None else channel.event_id,
                            technical_stream_id=(
                                stream.id if stream is not None else channel.technical_stream_id
                            ),
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
