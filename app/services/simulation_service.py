"""Orquestación de simulaciones locales sobre el motor puro de distribución."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.intelligence import ServerCostProfile, Simulation
from app.models.server import Server, ServerMetric
from app.repositories.server_repository import ServerRepository
from app.repositories.simulation_repository import SimulationRepository
from app.schemas.simulations import (
    DistributionAssignmentRead,
    DistributionServerRead,
    SimulationDataQuality,
    SimulationListRead,
    SimulationRead,
    SimulationRequest,
    SimulationResult,
    SimulationRisk,
)
from app.services.distribution_engine import (
    DistributionLoad,
    DistributionTarget,
    distribute_load,
)


@dataclass(frozen=True)
class _ServerContext:
    server: Server
    metric: ServerMetric | None
    cost: ServerCostProfile | None


def _effective_limit(value: float | None, fallback: float | None) -> float | None:
    return value if value is not None else fallback


class SimulationService:
    """Crea simulaciones guardadas localmente, sin efectos sobre recursos reales."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._servers = ServerRepository(session)
        self._simulations = SimulationRepository(session)

    def _contexts(self) -> dict[int, _ServerContext]:
        return {
            server.id: _ServerContext(server, metric, cost)
            for server, metric, cost in self._servers.latest_enabled_with_cost()
        }

    @staticmethod
    def _result_read(simulation: Simulation) -> SimulationRead:
        return SimulationRead(
            id=simulation.id,
            name=simulation.name,
            request=SimulationRequest.model_validate(simulation.request_payload),
            result=SimulationResult.model_validate(simulation.result_payload),
            created_at=simulation.created_at,
            updated_at=simulation.updated_at,
        )

    def list(self, page: int = 1, page_size: int = 50) -> SimulationListRead:
        items, total = self._simulations.list_page(page, page_size)
        return SimulationListRead(
            items=[self._result_read(item) for item in items],
            total=total,
        )

    def get(self, simulation_id: int) -> SimulationRead | None:
        simulation = self._simulations.get(simulation_id)
        return self._result_read(simulation) if simulation is not None else None

    def delete(self, simulation_id: int) -> bool:
        simulation = self._simulations.get(simulation_id)
        if simulation is None:
            return False
        self._simulations.delete(simulation)
        self._session.commit()
        return True

    def create(self, request: SimulationRequest) -> SimulationRead:
        contexts = self._contexts()
        override_by_id = {override.server_id: override for override in request.server_overrides}
        removed = set(request.removed_server_ids)
        included = (
            set(request.included_server_ids)
            if request.included_server_ids is not None
            else set(contexts)
        )
        missing_data: list[str] = []
        targets: list[DistributionTarget] = []
        current_costs: list[float | None] = []

        for server_id in sorted(included):
            context = contexts.get(server_id)
            if context is None:
                missing_data.append(f"server_id:{server_id}")
                continue
            override = override_by_id.get(server_id)
            if context.server.network_capacity_mbps is None:
                missing_data.append(f"capacity:{context.server.name}")
                continue
            physical = _effective_limit(
                override.physical_capacity_mbps if override else None,
                context.server.network_capacity_mbps,
            )
            operational = _effective_limit(
                override.operational_limit_mbps if override else None,
                context.server.operational_network_limit_mbps or physical,
            )
            recommended = _effective_limit(
                override.recommended_limit_mbps if override else None,
                context.server.recommended_network_limit_mbps or operational,
            )
            reserve = (
                override.minimum_reserve_mbps
                if override and override.minimum_reserve_mbps is not None
                else context.server.minimum_network_reserve_mbps or 0
            )
            if physical is None or operational is None or recommended is None:
                missing_data.append(f"limits:{context.server.name}")
                continue
            if server_id not in removed:
                targets.append(
                    DistributionTarget(
                        key=f"server:{server_id}",
                        name=context.server.name,
                        server_id=server_id,
                        capacity_mbps=physical,
                        operational_limit_mbps=operational,
                        recommended_limit_mbps=recommended,
                        minimum_reserve_mbps=reserve,
                    )
                )
            current_costs.append(context.cost.monthly_cost if context.cost else None)

        for virtual in request.virtual_servers:
            operational = virtual.operational_limit_mbps or virtual.physical_capacity_mbps
            recommended = virtual.recommended_limit_mbps or operational
            targets.append(
                DistributionTarget(
                    key=f"virtual:{virtual.key}",
                    name=virtual.name,
                    server_id=None,
                    capacity_mbps=virtual.physical_capacity_mbps,
                    operational_limit_mbps=operational,
                    recommended_limit_mbps=recommended,
                    minimum_reserve_mbps=virtual.minimum_reserve_mbps,
                )
            )

        if request.load_units is None:
            loads = [
                DistributionLoad(f"server-aggregate:{server_id}", metric.output_mbps)
                for server_id, context in contexts.items()
                if server_id in included and (metric := context.metric) is not None
            ]
            load_quality = SimulationDataQuality.OBSERVED
            if not loads:
                missing_data.append("latest_metrics")
        else:
            loads = [DistributionLoad(unit.id, unit.load_mbps) for unit in request.load_units]
            load_quality = SimulationDataQuality.SIMULATED

        distribution = distribute_load(targets, loads)
        if missing_data and load_quality == SimulationDataQuality.OBSERVED:
            data_quality = SimulationDataQuality.INSUFFICIENT_DATA
            risk = SimulationRisk.INSUFFICIENT_DATA
            explanation = "La simulación es preliminar porque faltan métricas o configuración."
        else:
            data_quality = load_quality
            risk = distribution.risk
            explanation = distribution.explanation
        if not loads and missing_data:
            feasible = False
        else:
            feasible = distribution.feasible and not missing_data

        proposed_costs: list[float | None] = []
        for target in targets:
            if target.server_id is None:
                virtual_key = target.key.removeprefix("virtual:")
                virtual = next(item for item in request.virtual_servers if item.key == virtual_key)
                proposed_costs.append(virtual.monthly_cost)
            else:
                context = contexts[target.server_id]
                override = override_by_id.get(target.server_id)
                proposed_costs.append(
                    override.monthly_cost
                    if override and override.monthly_cost is not None
                    else context.cost.monthly_cost
                    if context.cost
                    else None
                )
        current_monthly = (
            round(sum(item for item in current_costs if item is not None), 2)
            if current_costs and all(item is not None for item in current_costs)
            else None
        )
        proposed_monthly = (
            round(sum(item for item in proposed_costs if item is not None), 2)
            if proposed_costs and all(item is not None for item in proposed_costs)
            else None
        )
        savings = (
            round(current_monthly - proposed_monthly, 2)
            if current_monthly is not None and proposed_monthly is not None
            else None
        )
        result = SimulationResult(
            feasible=feasible,
            data_quality=data_quality,
            risk=risk,
            explanation=explanation,
            missing_data=sorted(set(missing_data)),
            servers=[
                DistributionServerRead(
                    key=item.target.key,
                    server_id=item.target.server_id,
                    name=item.target.name,
                    capacity_mbps=round(item.target.capacity_mbps, 2),
                    operational_limit_mbps=round(item.target.operational_limit_mbps, 2),
                    recommended_limit_mbps=round(item.target.recommended_limit_mbps, 2),
                    minimum_reserve_mbps=round(item.target.minimum_reserve_mbps, 2),
                    assigned_load_mbps=round(item.assigned_load_mbps, 2),
                    free_margin_mbps=round(item.free_margin_mbps, 2),
                    utilization_percent=round(
                        item.assigned_load_mbps / item.target.capacity_mbps * 100, 2
                    ),
                    assigned_unit_count=len(item.assigned_unit_ids),
                    exceeds_operational_target=item.assigned_load_mbps
                    > item.target.operational_limit_mbps,
                    exceeds_recommended_limit=item.assigned_load_mbps
                    > item.target.recommended_limit_mbps,
                )
                for item in distribution.targets
            ],
            assignments=[
                DistributionAssignmentRead(
                    unit_id=item.unit_id,
                    server_key=item.server_key,
                    load_mbps=round(item.load_mbps, 2),
                    assigned=item.assigned,
                    reason=item.reason,
                )
                for item in distribution.assignments
            ],
            unassigned_load_mbps=distribution.unassigned_load_mbps,
            unassigned_unit_count=sum(not item.assigned for item in distribution.assignments),
            total_capacity_mbps=round(
                sum(item.target.capacity_mbps for item in distribution.targets), 2
            ),
            total_assignable_capacity_mbps=round(
                sum(item.target.assignable_limit_mbps for item in distribution.targets), 2
            ),
            total_assigned_load_mbps=round(
                sum(item.assigned_load_mbps for item in distribution.targets), 2
            ),
            current_monthly_cost=current_monthly,
            proposed_monthly_cost=proposed_monthly,
            monthly_savings=savings,
            annual_savings=round(savings * 12, 2) if savings is not None else None,
        )
        request_payload = request.model_dump(mode="json")
        simulation = self._simulations.create(
            request.name,
            request_payload,
            result.model_dump(mode="json"),
        )
        self._session.commit()
        return self._result_read(simulation)
