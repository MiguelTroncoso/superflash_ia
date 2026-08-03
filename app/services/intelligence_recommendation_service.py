"""Reglas explicables de capacidad y costes; no usa IA ni ejecuta acciones."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.intelligence import PaymentStatus
from app.schemas.capacity import CapacityDataQuality, CapacityState
from app.schemas.intelligence import (
    IntelligenceRecommendation,
    IntelligenceRecommendationsRead,
    IntelligenceSeverity,
)
from app.schemas.simulations import SimulationDataQuality
from app.services.capacity_service import CapacityService
from app.services.cost_service import CostService


class IntelligenceRecommendationService:
    """Evalúa reglas deterministas sobre una fotografía de la infraestructura."""

    def __init__(self, session: Session) -> None:
        self._capacity = CapacityService(session)
        self._costs = CostService(session)

    def evaluate(self) -> IntelligenceRecommendationsRead:
        now = datetime.now(UTC)
        capacity = self._capacity.build()
        costs = self._costs.build()
        recommendations: list[IntelligenceRecommendation] = []
        profile_by_server = {profile.server_id: profile for profile in costs.profiles}

        for server in capacity.servers:
            if server.state == CapacityState.NO_DATA:
                recommendations.append(
                    IntelligenceRecommendation(
                        code="insufficient_data",
                        severity=IntelligenceSeverity.WARNING,
                        title=f"Datos insuficientes para {server.name}",
                        explanation=(
                            "No se puede estimar capacidad con confianza sin una muestra "
                            "reciente y límites configurados."
                        ),
                        data_used=["server_inventory", "latest_server_metric"],
                        monthly_savings=None,
                        annual_savings=None,
                        risk="high",
                        confidence=0.2,
                        suggested_action=(
                            "Configurar capacidad y esperar una recolección válida; no se "
                            "ejecuta ninguna acción automáticamente."
                        ),
                        server_id=server.server_id,
                        server_name=server.name,
                    )
                )
                continue
            if server.state == CapacityState.CRITICAL:
                recommendations.append(
                    IntelligenceRecommendation(
                        code="over_maximum_capacity",
                        severity=IntelligenceSeverity.CRITICAL,
                        title=f"{server.name} supera el límite recomendado",
                        explanation=(
                            "La carga observada excede el máximo recomendado o la capacidad "
                            "física configurada."
                        ),
                        data_used=[
                            "latest_server_metric.output_mbps",
                            "recommended_limit_mbps",
                            "physical_capacity_mbps",
                        ],
                        monthly_savings=None,
                        annual_savings=None,
                        risk="high",
                        confidence=0.95,
                        suggested_action=(
                            "Revisar distribución y capacidad disponible antes de realizar "
                            "cambios operativos."
                        ),
                        server_id=server.server_id,
                        server_name=server.name,
                    )
                )
            elif server.state == CapacityState.HIGH:
                recommendations.append(
                    IntelligenceRecommendation(
                        code="over_operational_target",
                        severity=IntelligenceSeverity.WARNING,
                        title=f"{server.name} supera su objetivo operativo",
                        explanation=(
                            "La carga sigue dentro del máximo recomendado, pero ya superó el "
                            "objetivo operativo configurado."
                        ),
                        data_used=["latest_server_metric.output_mbps", "operational_limit_mbps"],
                        monthly_savings=None,
                        annual_savings=None,
                        risk="medium",
                        confidence=0.9,
                        suggested_action="Revisar una redistribución en modo simulación.",
                        server_id=server.server_id,
                        server_name=server.name,
                    )
                )
            if (
                server.operational_utilization_percent is not None
                and server.operational_utilization_percent <= 20
                and server.server_id in profile_by_server
            ):
                recommendations.append(
                    IntelligenceRecommendation(
                        code="underutilized",
                        severity=IntelligenceSeverity.INFO,
                        title=f"{server.name} está infrautilizado",
                        explanation=(
                            "La última carga observada está por debajo del 20% del objetivo "
                            "operativo."
                        ),
                        data_used=[
                            "latest_server_metric.output_mbps",
                            "operational_limit_mbps",
                            "monthly_cost",
                        ],
                        monthly_savings=None,
                        annual_savings=None,
                        risk="low",
                        confidence=0.8,
                        suggested_action=(
                            "Evaluar consolidación o reemplazo mediante una simulación antes "
                            "de actuar."
                        ),
                        server_id=server.server_id,
                        server_name=server.name,
                    )
                )

        for payment in costs.upcoming:
            if payment.payment_status not in {PaymentStatus.DUE_SOON, PaymentStatus.OVERDUE}:
                continue
            overdue = payment.payment_status == PaymentStatus.OVERDUE
            recommendations.append(
                IntelligenceRecommendation(
                    code="payment_overdue" if overdue else "payment_due",
                    severity=IntelligenceSeverity.CRITICAL
                    if overdue
                    else IntelligenceSeverity.WARNING,
                    title=f"Pago {'vencido' if overdue else 'próximo'}: {payment.server_name}",
                    explanation=(
                        f"El coste informativo de {payment.amount:.2f} {payment.currency} "
                        f"tiene fecha {payment.next_payment_date.isoformat()}."
                    ),
                    data_used=["next_payment_date", "monthly_cost", "payment_status"],
                    monthly_savings=None,
                    annual_savings=None,
                    risk="medium" if not overdue else "high",
                    confidence=1.0,
                    suggested_action=(
                        "Verificar el pago en el proveedor por el canal administrativo "
                        "correspondiente."
                    ),
                    server_id=payment.server_id,
                    server_name=payment.server_name,
                )
            )

        if capacity.data_quality == CapacityDataQuality.INSUFFICIENT_DATA:
            recommendations.append(
                IntelligenceRecommendation(
                    code="insufficient_data",
                    severity=IntelligenceSeverity.WARNING,
                    title="La capacidad global es preliminar",
                    explanation=(
                        "Al menos un servidor habilitado no tiene métrica o configuración "
                        "suficiente."
                    ),
                    data_used=[
                        "server_inventory",
                        "latest_server_metric",
                        "capacity_configuration",
                    ],
                    monthly_savings=None,
                    annual_savings=None,
                    risk="high",
                    confidence=0.35,
                    suggested_action=(
                        "Completar la configuración y validar la recolección antes de tomar "
                        "decisiones."
                    ),
                )
            )
        elif capacity.total_observed_load_mbps > capacity.total_operational_limit_mbps:
            recommendations.append(
                IntelligenceRecommendation(
                    code="insufficient_capacity",
                    severity=IntelligenceSeverity.CRITICAL,
                    title="Capacidad operativa insuficiente",
                    explanation=(
                        "La carga agregada observada supera la suma de objetivos operativos "
                        "configurados."
                    ),
                    data_used=["latest_server_metric.output_mbps", "operational_limit_mbps"],
                    monthly_savings=None,
                    annual_savings=None,
                    risk="high",
                    confidence=0.9,
                    suggested_action=(
                        "Simular capacidad adicional o redistribución; el monitor no mueve cargas."
                    ),
                )
            )

        if capacity.server_count > 1 and capacity.total_operational_free_mbps > 0:
            recommendations.append(
                IntelligenceRecommendation(
                    code="consolidation_candidate",
                    severity=IntelligenceSeverity.INFO,
                    title="Existe margen para evaluar consolidación",
                    explanation=(
                        "Hay margen operativo agregado; una simulación puede estimar si una "
                        "reducción es factible."
                    ),
                    data_used=[
                        "operational_limit_mbps",
                        "latest_server_metric.output_mbps",
                        "server_count",
                    ],
                    monthly_savings=None,
                    annual_savings=None,
                    risk="medium",
                    confidence=0.65,
                    suggested_action="Comparar escenarios sin modificar el inventario real.",
                )
            )

        data_quality = (
            SimulationDataQuality.OBSERVED
            if capacity.data_quality == CapacityDataQuality.OBSERVED
            else SimulationDataQuality.INSUFFICIENT_DATA
        )
        return IntelligenceRecommendationsRead(
            generated_at=now,
            data_quality=data_quality,
            recommendations=recommendations,
        )
