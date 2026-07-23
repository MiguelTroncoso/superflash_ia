"""Endpoint de healthcheck."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.schemas.health import HealthRead

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthRead)
def health(
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthRead:
    """Informa el estado de la aplicación, la base de datos y la versión.

    Devuelve siempre 200 con el detalle en el cuerpo: un orquestador
    puede decidir según ``status`` sin perder la información de qué
    dependencia falló.
    """
    database: str = "ok"
    try:
        session.execute(text("SELECT 1"))
    except Exception:  # el healthcheck nunca debe propagar errores de conexión
        logger.exception("healthcheck: fallo de conexión con la base de datos")
        database = "error"

    return HealthRead(
        status="ok" if database == "ok" else "degraded",
        database="ok" if database == "ok" else "error",
        version=settings.app_version,
    )
