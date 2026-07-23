"""Router agregado de la versión 1 de la API.

Toda la versión 1 exige la cabecera ``X-API-Key`` (ver
``require_api_key``); únicamente ``/health`` queda fuera y es público.
"""

from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.api.v1 import alerts, channels, collection, overview, servers

api_v1_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])
api_v1_router.include_router(servers.router)
api_v1_router.include_router(channels.router)
api_v1_router.include_router(collection.router)
api_v1_router.include_router(overview.router)
api_v1_router.include_router(alerts.router)
