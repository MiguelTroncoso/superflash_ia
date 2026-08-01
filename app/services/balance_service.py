"""Balance de utilización y capacidad de la infraestructura."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.repositories.server_repository import ServerRepository
from app.schemas.balance import BalanceRead, BalanceServerRead
from app.services.overview_service import compute_network_utilization


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


class BalanceService:
    """Calcula agregados sin escribir en la base de datos."""

    def __init__(self, session: Session) -> None:
        self._servers = ServerRepository(session)

    def build(self) -> BalanceRead:
        latest = self._servers.latest_metrics_for_enabled()
        rows = [
            BalanceServerRead(
                server_id=server.id,
                name=server.name,
                output_mbps=round(metric.output_mbps, 2),
                capacity_mbps=server.network_capacity_mbps,
                utilization_percent=compute_network_utilization(
                    metric.output_mbps, server.network_capacity_mbps
                ),
            )
            for server, metric in latest
        ]
        utilization = [
            row.utilization_percent for row in rows if row.utilization_percent is not None
        ]
        capacity_total = round(sum(server.network_capacity_mbps or 0 for server, _ in latest), 2)
        output_total = round(sum(metric.output_mbps for _, metric in latest), 2)
        capacity_used = round(min(output_total, capacity_total), 2)
        capacity_free = round(max(capacity_total - capacity_used, 0), 2)
        by_utilization = [row for row in rows if row.utilization_percent is not None]
        most_loaded = max(
            by_utilization, key=lambda row: row.utilization_percent or 0, default=None
        )
        least_utilized = min(
            by_utilization, key=lambda row: row.utilization_percent or 0, default=None
        )

        return BalanceRead(
            generated_at=datetime.now(UTC),
            server_count=self._servers.count_enabled(),
            sampled_server_count=len(latest),
            average_cpu_percent=_average([metric.cpu_percent for _, metric in latest]),
            average_memory_percent=_average([metric.memory_percent for _, metric in latest]),
            average_network_mbps=_average([metric.output_mbps for _, metric in latest]),
            average_network_utilization_percent=_average(utilization),
            average_disk_percent=_average(
                [metric.disk_percent for _, metric in latest if metric.disk_percent is not None]
            ),
            capacity_total_mbps=capacity_total,
            capacity_used_mbps=capacity_used,
            capacity_free_mbps=capacity_free,
            most_loaded=most_loaded,
            least_utilized=least_utilized,
            servers=rows,
        )
