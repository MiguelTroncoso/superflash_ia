"""Punto de entrada de la aplicación FastAPI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.logging import setup_logging


def create_app() -> FastAPI:
    """Construye la aplicación con routers, CORS y logging configurados."""
    settings = get_settings()
    setup_logging(settings.log_level)

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Plataforma privada de monitoreo de solo lectura. "
            "La versión actual utiliza únicamente datos simulados y no "
            "modifica ninguna infraestructura externa."
        ),
    )

    # CORS solo se habilita con una lista explícita de orígenes; nunca "*"
    # de forma indiscriminada en producción.
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    application.include_router(health_router)
    application.include_router(api_v1_router)
    return application


app = create_app()
