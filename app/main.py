"""Punto de entrada de la aplicación FastAPI."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.factory import get_adapter
from app.api.health import router as health_router
from app.api.v1.router import api_v1_router
from app.collectors.runner import get_collection_runner
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.session import get_session_factory
from app.tasks.scheduler import CollectionScheduler, set_active_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Arranca y detiene el scheduler periódico si está habilitado."""
    settings = get_settings()
    scheduler: CollectionScheduler | None = None
    if settings.scheduler_enabled:
        scheduler = CollectionScheduler(
            interval_seconds=settings.collection_interval_seconds,
            session_factory=get_session_factory(),
            adapter_factory=lambda: get_adapter(settings),
            runner=get_collection_runner(),
            collection_timeout_seconds=settings.collection_timeout_seconds,
        )
        scheduler.start()
        set_active_scheduler(scheduler)
    else:
        logger.info("scheduler deshabilitado (SCHEDULER_ENABLED=false)")
    try:
        yield
    finally:
        if scheduler is not None:
            await scheduler.stop()
            set_active_scheduler(None)


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
        lifespan=lifespan,
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
