"""Endpoints del motor de capacidad, costes y simulación local."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.capacity import CapacityOverviewRead, CapacityServerRead
from app.schemas.costs import CostsSummaryRead, UpcomingPaymentRead
from app.schemas.intelligence import IntelligenceRecommendationsRead
from app.schemas.simulations import (
    SimulationListRead,
    SimulationRead,
    SimulationRequest,
)
from app.services.capacity_service import CapacityService
from app.services.cost_service import CostService
from app.services.intelligence_recommendation_service import IntelligenceRecommendationService
from app.services.simulation_service import SimulationService

router = APIRouter(tags=["infrastructure-intelligence"])


@router.get("/costs/summary", response_model=CostsSummaryRead)
def get_costs_summary(session: Annotated[Session, Depends(get_db)]) -> CostsSummaryRead:
    return CostService(session).build()


@router.get("/costs/upcoming", response_model=list[UpcomingPaymentRead])
def get_upcoming_costs(
    session: Annotated[Session, Depends(get_db)],
    days: Annotated[int, Query(ge=0, le=365)] = 30,
) -> list[UpcomingPaymentRead]:
    return CostService(session).upcoming(days)


@router.get("/capacity/overview", response_model=CapacityOverviewRead)
def get_capacity_overview(session: Annotated[Session, Depends(get_db)]) -> CapacityOverviewRead:
    return CapacityService(session).build()


@router.get("/capacity/servers", response_model=list[CapacityServerRead])
def get_capacity_servers(session: Annotated[Session, Depends(get_db)]) -> list[CapacityServerRead]:
    return CapacityService(session).list_servers()


@router.post("/simulations", response_model=SimulationRead, status_code=status.HTTP_201_CREATED)
def create_simulation(
    payload: SimulationRequest,
    session: Annotated[Session, Depends(get_db)],
) -> SimulationRead:
    return SimulationService(session).create(payload)


@router.get("/simulations", response_model=SimulationListRead)
def list_simulations(
    session: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> SimulationListRead:
    return SimulationService(session).list(page, page_size)


@router.get("/simulations/{simulation_id}", response_model=SimulationRead)
def get_simulation(
    simulation_id: int,
    session: Annotated[Session, Depends(get_db)],
) -> SimulationRead:
    simulation = SimulationService(session).get(simulation_id)
    if simulation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Simulación no encontrada"
        )
    return simulation


@router.delete("/simulations/{simulation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_simulation(
    simulation_id: int,
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    if not SimulationService(session).delete(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Simulación no encontrada"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/intelligence/recommendations", response_model=IntelligenceRecommendationsRead)
def get_intelligence_recommendations(
    session: Annotated[Session, Depends(get_db)],
) -> IntelligenceRecommendationsRead:
    return IntelligenceRecommendationService(session).evaluate()
