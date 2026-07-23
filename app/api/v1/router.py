"""Router agregado de la versión 1 de la API."""

from fastapi import APIRouter

from app.api.v1 import channels, collection, overview, servers

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(servers.router)
api_v1_router.include_router(channels.router)
api_v1_router.include_router(collection.router)
api_v1_router.include_router(overview.router)
