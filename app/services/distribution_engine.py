"""Motor puro de distribución; no conoce SQL ni ejecuta cambios."""

from dataclasses import dataclass, field

from app.schemas.simulations import SimulationRisk


@dataclass(frozen=True)
class DistributionLoad:
    """Unidad de carga ordenable por el motor."""

    id: str
    load_mbps: float


@dataclass(frozen=True)
class DistributionTarget:
    """Capacidad disponible de un servidor real o virtual."""

    key: str
    name: str
    server_id: int | None
    capacity_mbps: float
    operational_limit_mbps: float
    recommended_limit_mbps: float
    minimum_reserve_mbps: float = 0

    @property
    def assignable_limit_mbps(self) -> float:
        return max(self.recommended_limit_mbps - self.minimum_reserve_mbps, 0)


@dataclass
class DistributionTargetResult:
    target: DistributionTarget
    assigned_load_mbps: float = 0
    assigned_unit_ids: list[str] = field(default_factory=list)

    @property
    def free_margin_mbps(self) -> float:
        return max(self.target.assignable_limit_mbps - self.assigned_load_mbps, 0)


@dataclass(frozen=True)
class DistributionAssignment:
    unit_id: str
    server_key: str | None
    load_mbps: float
    assigned: bool
    reason: str | None = None


@dataclass
class DistributionResult:
    targets: list[DistributionTargetResult]
    assignments: list[DistributionAssignment]
    unassigned_load_mbps: float
    risk: SimulationRisk
    explanation: str

    @property
    def feasible(self) -> bool:
        return self.unassigned_load_mbps <= 0.000001


def distribute_load(
    targets: list[DistributionTarget], loads: list[DistributionLoad]
) -> DistributionResult:
    """Asigna primero las unidades mayores a la mejor holgura disponible.

    El límite efectivo es el recomendado menos la reserva mínima. No existe
    ningún límite fijo por tipo de servidor: toda regla proviene de la
    configuración recibida en ``DistributionTarget``.
    """

    results = [
        DistributionTargetResult(target=target) for target in sorted(targets, key=lambda t: t.key)
    ]
    assignments: list[DistributionAssignment] = []
    unassigned_load = 0.0
    for load in sorted(loads, key=lambda item: (-item.load_mbps, item.id)):
        candidates = [
            result
            for result in results
            if result.assigned_load_mbps + load.load_mbps
            <= result.target.assignable_limit_mbps + 0.000001
        ]
        if not candidates:
            unassigned_load += load.load_mbps
            assignments.append(
                DistributionAssignment(
                    unit_id=load.id,
                    server_key=None,
                    load_mbps=load.load_mbps,
                    assigned=False,
                    reason="No existe margen suficiente dentro de los límites configurados.",
                )
            )
            continue
        selected = max(candidates, key=lambda item: (item.free_margin_mbps, item.target.key))
        selected.assigned_load_mbps += load.load_mbps
        selected.assigned_unit_ids.append(load.id)
        assignments.append(
            DistributionAssignment(
                unit_id=load.id,
                server_key=selected.target.key,
                load_mbps=load.load_mbps,
                assigned=True,
            )
        )

    if unassigned_load > 0:
        risk = SimulationRisk.HIGH
        explanation = "La distribución no es factible: parte de la carga quedó sin servidor."
    elif any(
        result.assigned_load_mbps > result.target.operational_limit_mbps + 0.000001
        for result in results
    ):
        risk = SimulationRisk.MEDIUM
        explanation = (
            "La distribución es factible, pero supera el objetivo operativo de algún servidor."
        )
    else:
        risk = SimulationRisk.LOW
        explanation = "La distribución es factible dentro de los límites y reservas configurados."
    return DistributionResult(results, assignments, round(unassigned_load, 2), risk, explanation)
