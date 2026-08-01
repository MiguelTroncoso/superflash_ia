"""Endpoints de alertas persistentes y su ciclo de vida."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.models.alert import AlertStatus
from app.repositories.alert_repository import AlertRepository
from app.schemas.alerts import AlertRead, AlertsRead, AlertUpdate
from app.services.alert_service import AlertService

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=AlertsRead)
def list_alerts(
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AlertsRead:
    """Alertas activas según las últimas muestras y los umbrales configurados.

    La evaluación sincroniza el estado local, pero nunca modifica la fuente
    externa ni envía notificaciones.
    """
    return AlertService(session, settings).evaluate()


@router.patch("/alerts/{alert_id}", response_model=AlertRead)
def update_alert(
    alert_id: int,
    payload: AlertUpdate,
    session: Annotated[Session, Depends(get_db)],
) -> AlertRead:
    """Marca una alerta como activa, acknowledged o resolved."""
    alert = AlertRepository(session).get(alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta no encontrada")
    now = datetime.now(UTC)
    alert.status = payload.status
    alert.acknowledged_at = now if payload.status is AlertStatus.ACKNOWLEDGED else None
    alert.resolved_at = now if payload.status is AlertStatus.RESOLVED else None
    session.commit()
    return AlertService._read(alert)
