"""Motor de reglas deterministas para recomendaciones de infraestructura."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.timeutils import ensure_utc
from app.repositories.server_repository import ServerRepository
from app.schemas.recommendations import (
    RecommendationRead,
    RecommendationSeverity,
    RecommendationsRead,
    RecommendationType,
)
from app.services.overview_service import compute_network_utilization


class RecommendationService:
    """Evalúa reglas simples sin IA ni efectos secundarios."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._servers = ServerRepository(session)
        self._settings = settings

    def evaluate(self) -> RecommendationsRead:
        now = datetime.now(UTC)
        recommendations: list[RecommendationRead] = []
        latest_by_server = {
            server.id: (server, metric)
            for server, metric in self._servers.latest_metrics_for_enabled()
        }

        for server in self._servers.list_all():
            if not server.enabled:
                continue
            entry = latest_by_server.get(server.id)
            if entry is None:
                recommendations.append(
                    self._item(
                        RecommendationType.NO_DATA,
                        RecommendationSeverity.CRITICAL,
                        server.id,
                        server.name,
                        "Servidor sin datos",
                        "No existe ninguna métrica persistida para este servidor.",
                        now,
                    )
                )
                continue

            _, metric = entry
            collected_at = ensure_utc(metric.collected_at)
            age = now - collected_at
            if age > timedelta(minutes=self._settings.alert_stale_minutes):
                recommendations.append(
                    self._item(
                        RecommendationType.HEARTBEAT_LOST,
                        RecommendationSeverity.CRITICAL,
                        server.id,
                        server.name,
                        "Heartbeat perdido",
                        f"La última muestra tiene {int(age.total_seconds() // 60)} minutos.",
                        now,
                        value=round(age.total_seconds() / 60, 1),
                        threshold=float(self._settings.alert_stale_minutes),
                    )
                )

            checks = (
                (RecommendationType.HIGH_CPU, "CPU", metric.cpu_percent),
                (RecommendationType.HIGH_MEMORY, "RAM", metric.memory_percent),
                (RecommendationType.HIGH_DISK, "Disco", metric.disk_percent),
                (
                    RecommendationType.HIGH_NETWORK,
                    "Red",
                    compute_network_utilization(metric.output_mbps, server.network_capacity_mbps),
                ),
            )
            for recommendation_type, label, value in checks:
                if value is None or value <= 90:
                    continue
                severity = (
                    RecommendationSeverity.CRITICAL
                    if value >= 95
                    else RecommendationSeverity.WARNING
                )
                recommendations.append(
                    self._item(
                        recommendation_type,
                        severity,
                        server.id,
                        server.name,
                        f"{label} sobre 90%",
                        f"{label} actual: {value:.1f}%.",
                        now,
                        value=value,
                        threshold=90,
                    )
                )

            utilization = compute_network_utilization(
                metric.output_mbps, server.network_capacity_mbps
            )
            if utilization is not None and utilization < 10 and metric.cpu_percent < 20:
                recommendations.append(
                    self._item(
                        RecommendationType.UNDERUTILIZED,
                        RecommendationSeverity.INFO,
                        server.id,
                        server.name,
                        "Servidor infrautilizado",
                        "La utilización combinada de red y CPU es baja.",
                        now,
                        value=utilization,
                        threshold=10,
                    )
                )

        return RecommendationsRead(generated_at=now, recommendations=recommendations)

    @staticmethod
    def _item(
        recommendation_type: RecommendationType,
        severity: RecommendationSeverity,
        server_id: int,
        server_name: str,
        title: str,
        message: str,
        generated_at: datetime,
        value: float | None = None,
        threshold: float | None = None,
    ) -> RecommendationRead:
        return RecommendationRead(
            type=recommendation_type,
            severity=severity,
            server_id=server_id,
            server_name=server_name,
            title=title,
            message=message,
            value=value,
            threshold=threshold,
            generated_at=generated_at,
        )
