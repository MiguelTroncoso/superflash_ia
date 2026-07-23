"""Endpoint interno para disparar la recolección manualmente.

ADVERTENCIA: endpoint de uso interno/operativo. Hoy no requiere
autenticación porque la aplicación se despliega en una red privada;
antes de exponerla fuera de ese perímetro debe protegerse (p. ej. token
estático via cabecera, definido por variable de entorno). El punto de
enganche previsto es una dependencia de FastAPI en este router.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.adapters.factory import get_adapter
from app.api.deps import get_db
from app.collectors.collection import CollectionService
from app.core.config import Settings, get_settings
from app.schemas.collection import CollectionResult

router = APIRouter(prefix="/collection", tags=["collection (interno)"])


@router.post("/run", response_model=CollectionResult)
def run_collection(
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CollectionResult:
    """Ejecuta una recolección con el adaptador configurado (mock).

    Operación de solo lectura hacia la fuente externa; únicamente
    escribe en la base de datos propia de la plataforma.
    """
    adapter = get_adapter(settings)
    return CollectionService(session, adapter).run()
