"""Endpoint de alertas internas de solo lectura."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.schemas.alerts import AlertsRead
from app.services.alert_service import AlertService

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=AlertsRead)
def list_alerts(
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AlertsRead:
    """Alertas activas según las últimas muestras y los umbrales configurados.

    Evaluación bajo demanda: no se persiste nada ni se envían
    notificaciones externas.
    """
    return AlertService(session, settings).evaluate()
