"""Alertas internas de solo lectura, evaluadas bajo demanda.

Se calculan sobre la última muestra persistida de cada servidor
habilitado comparándola con los umbrales configurados. No se envían
notificaciones externas ni se persiste nada: son un diagnóstico
consultable por ``GET /api/v1/alerts``.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.timeutils import ensure_utc
from app.models.server import Server, ServerMetric
from app.repositories.server_repository import ServerRepository
from app.schemas.alerts import AlertRead, AlertsRead, AlertType
from app.services.overview_service import compute_network_utilization


class AlertService:
    """Evalúa los umbrales configurados contra las últimas muestras."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._servers = ServerRepository(session)
        self._settings = settings

    def evaluate(self) -> AlertsRead:
        """Calcula las alertas activas en este instante."""
        now = datetime.now(UTC)
        alerts: list[AlertRead] = []

        latest_by_server = {
            server.id: (server, metric)
            for server, metric in self._servers.latest_metrics_for_enabled()
        }

        for server in self._servers.list_all():
            if not server.enabled:
                continue
            entry = latest_by_server.get(server.id)
            if entry is None:
                alerts.append(
                    AlertRead(
                        type=AlertType.STALE_SERVER,
                        server_id=server.id,
                        server_name=server.name,
                        message="El servidor no tiene ninguna muestra registrada",
                    )
                )
                continue
            _, metric = entry
            alerts.extend(self._evaluate_metric(server, metric, now))

        return AlertsRead(generated_at=now, alerts=alerts)

    def _evaluate_metric(
        self, server: Server, metric: ServerMetric, now: datetime
    ) -> list[AlertRead]:
        """Alertas derivadas de la última muestra de un servidor."""
        settings = self._settings
        collected_at = ensure_utc(metric.collected_at)
        alerts: list[AlertRead] = []

        age = now - collected_at
        if age > timedelta(minutes=settings.alert_stale_minutes):
            alerts.append(
                AlertRead(
                    type=AlertType.STALE_SERVER,
                    server_id=server.id,
                    server_name=server.name,
                    message=(f"Sin muestras desde hace {int(age.total_seconds() // 60)} minutos"),
                    value=round(age.total_seconds() / 60, 1),
                    threshold=float(settings.alert_stale_minutes),
                    collected_at=collected_at,
                )
            )

        checks: list[tuple[AlertType, float | None, float, str]] = [
            (AlertType.HIGH_CPU, metric.cpu_percent, settings.alert_cpu_percent, "CPU"),
            (
                AlertType.HIGH_MEMORY,
                metric.memory_percent,
                settings.alert_memory_percent,
                "Memoria",
            ),
            (AlertType.HIGH_DISK, metric.disk_percent, settings.alert_disk_percent, "Disco"),
            (
                AlertType.HIGH_NETWORK_UTILIZATION,
                compute_network_utilization(metric.output_mbps, server.network_capacity_mbps),
                settings.alert_network_utilization_percent,
                "Utilización de red",
            ),
        ]
        for alert_type, value, threshold, label in checks:
            # value None = la fuente no entrega ese dato (p. ej. disco en el
            # mock combinado, o capacidad de red desconocida): no se alerta.
            if value is not None and value > threshold:
                alerts.append(
                    AlertRead(
                        type=alert_type,
                        server_id=server.id,
                        server_name=server.name,
                        message=f"{label} en {value}% supera el umbral de {threshold}%",
                        value=value,
                        threshold=threshold,
                        collected_at=collected_at,
                    )
                )
        return alerts
