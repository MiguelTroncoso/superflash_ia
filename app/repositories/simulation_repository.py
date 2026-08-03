"""Persistencia del historial local de simulaciones."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.intelligence import Simulation


class SimulationRepository:
    """CRUD local de simulaciones; nunca modifica inventario o infraestructura."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_page(self, page: int, page_size: int) -> tuple[list[Simulation], int]:
        total = int(self._session.scalar(select(func.count(Simulation.id))) or 0)
        stmt = (
            select(Simulation)
            .order_by(Simulation.created_at.desc(), Simulation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self._session.scalars(stmt)), total

    def get(self, simulation_id: int) -> Simulation | None:
        return self._session.get(Simulation, simulation_id)

    def create(
        self, name: str, request_payload: dict[str, object], result_payload: dict[str, object]
    ) -> Simulation:
        simulation = Simulation(
            name=name,
            request_payload=request_payload,
            result_payload=result_payload,
        )
        self._session.add(simulation)
        self._session.flush()
        return simulation

    def delete(self, simulation: Simulation) -> None:
        self._session.delete(simulation)
        self._session.flush()
