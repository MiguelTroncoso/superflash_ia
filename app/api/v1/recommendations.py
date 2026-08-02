"""Endpoint de recomendaciones deterministas."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.schemas.recommendations import RecommendationsRead
from app.services.recommendation_service import RecommendationService

router = APIRouter(tags=["recommendations"])


@router.get("/recommendations", response_model=RecommendationsRead)
def get_recommendations(
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RecommendationsRead:
    """Evalúa recomendaciones sin modificar infraestructura ni persistencia."""
    return RecommendationService(session, settings).evaluate()
