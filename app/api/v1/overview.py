"""Endpoint del resumen agregado de la infraestructura."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.overview import OverviewRead
from app.services.overview_service import OverviewService

router = APIRouter(tags=["overview"])


@router.get("/overview", response_model=OverviewRead)
def get_overview(session: Annotated[Session, Depends(get_db)]) -> OverviewRead:
    """Estadísticas globales calculadas sobre las muestras más recientes."""
    return OverviewService(session).build()
