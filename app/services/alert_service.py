"""Alertas internas persistidas y evaluadas contra las últimas métricas."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.timeutils import ensure_utc
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.server import Server, ServerMetric
from app.repositories.alert_repository import AlertRepository
from app.repositories.server_repository import ServerRepository
from app.schemas.alerts import AlertRead, AlertsRead, AlertType
from app.services.overview_service import compute_network_utilization


class AlertService:
    """Evalúa umbrales y sincroniza el ciclo de vida de cada alerta."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._servers = ServerRepository(session)
        self._alerts = AlertRepository(session)
        self._settings = settings

    def evaluate(self) -> AlertsRead:
        """Calcula alertas activas y persiste sus transiciones."""
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

        return AlertsRead(generated_at=now, alerts=self._sync(alerts, now))

    def _sync(self, candidates: list[AlertRead], now: datetime) -> list[AlertRead]:
        """Upserta reglas activas y resuelve las que dejaron de cumplirse."""
        fingerprints: set[str] = set()
        current: list[AlertRead] = []
        for candidate in candidates:
            fingerprint = f"{candidate.server_id}:{candidate.type.value}"
            fingerprints.add(fingerprint)
            alert = self._alerts.get_by_fingerprint(fingerprint)
            fields = {
                "fingerprint": fingerprint,
                "type": candidate.type.value,
                "severity": self._severity(candidate),
                "server_id": candidate.server_id,
                "server_name": candidate.server_name,
                "message": candidate.message,
                "value": candidate.value,
                "threshold": candidate.threshold,
                "collected_at": candidate.collected_at,
                "last_seen_at": now,
            }
            if alert is None:
                alert = self._alerts.create(
                    {
                        **fields,
                        "status": AlertStatus.ACTIVE,
                        "first_seen_at": now,
                    }
                )
            else:
                acknowledged = alert.status is AlertStatus.ACKNOWLEDGED
                resolved = alert.status is AlertStatus.RESOLVED
                for name, value in fields.items():
                    setattr(alert, name, value)
                if resolved:
                    alert.status = AlertStatus.ACTIVE
                    alert.acknowledged_at = None
                    alert.resolved_at = None
                elif not acknowledged:
                    alert.status = AlertStatus.ACTIVE
            current.append(self._read(alert))

        for alert in self._alerts.list_current():
            if alert.fingerprint not in fingerprints:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = now
        self._session.commit()
        return current

    @staticmethod
    def _severity(candidate: AlertRead) -> AlertSeverity:
        if candidate.type in {AlertType.HIGH_CPU, AlertType.HIGH_MEMORY, AlertType.HIGH_DISK}:
            return AlertSeverity.CRITICAL if (candidate.value or 0) >= 95 else AlertSeverity.WARNING
        return AlertSeverity.WARNING

    @staticmethod
    def _read(alert: Alert) -> AlertRead:
        return AlertRead(
            id=alert.id,
            type=AlertType(alert.type),
            severity=alert.severity,
            status=alert.status,
            server_id=alert.server_id,
            server_name=alert.server_name,
            message=alert.message,
            value=alert.value,
            threshold=alert.threshold,
            collected_at=alert.collected_at,
            first_seen_at=alert.first_seen_at,
            last_seen_at=alert.last_seen_at,
            acknowledged_at=alert.acknowledged_at,
            resolved_at=alert.resolved_at,
        )

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
