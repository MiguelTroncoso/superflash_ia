"""Ejecución serializada de recolecciones con estado observable.

Un único ``CollectionRunner`` por proceso garantiza que nunca haya dos
recolecciones simultáneas (lock no bloqueante) y registra el estado de
la última ejecución para el endpoint de status.

Limitación conocida y documentada: el estado y el lock viven en memoria
del proceso, por lo que solo protegen un despliegue de una única
instancia de la API. Con varias réplicas se necesitará un lock a nivel
de base de datos (p. ej. ``pg_advisory_lock``).
"""

import logging
import threading
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.adapters.base import MonitoringSourceAdapter
from app.collectors.collection import CollectionService
from app.schemas.collection import CollectionLastRun, CollectionResult

logger = logging.getLogger(__name__)


class CollectionAlreadyRunningError(RuntimeError):
    """Se intentó iniciar una recolección mientras otra estaba en curso."""


class CollectionRunner:
    """Serializa las recolecciones y expone su estado."""

    def __init__(self) -> None:
        self._run_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._running_since: datetime | None = None
        self._last_run: CollectionLastRun | None = None

    @property
    def is_running(self) -> bool:
        """Indica si hay una recolección en curso en este proceso."""
        with self._state_lock:
            return self._running_since is not None

    @property
    def running_since(self) -> datetime | None:
        """Instante de inicio de la recolección en curso, si la hay."""
        with self._state_lock:
            return self._running_since

    @property
    def last_run(self) -> CollectionLastRun | None:
        """Resumen de la última recolección terminada, si existe."""
        with self._state_lock:
            return self._last_run

    def run(self, session: Session, adapter: MonitoringSourceAdapter) -> CollectionResult:
        """Ejecuta una recolección si no hay otra en curso.

        Raises:
            CollectionAlreadyRunningError: Si ya hay una recolección
                activa en este proceso.
        """
        if not self._run_lock.acquire(blocking=False):
            raise CollectionAlreadyRunningError("ya hay una recolección en curso")

        started_at = datetime.now(UTC)
        with self._state_lock:
            self._running_since = started_at

        result: CollectionResult | None = None
        error: str | None = None
        try:
            result = CollectionService(session, adapter).run()
            return result
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            finished_at = datetime.now(UTC)
            with self._state_lock:
                self._running_since = None
                self._last_run = CollectionLastRun(
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=round((finished_at - started_at).total_seconds(), 3),
                    success=error is None,
                    error=error,
                    result=result,
                )
            self._run_lock.release()

    def reset(self) -> None:
        """Limpia el estado registrado (uso exclusivo en tests)."""
        with self._state_lock:
            self._running_since = None
            self._last_run = None


_runner = CollectionRunner()


def get_collection_runner() -> CollectionRunner:
    """Devuelve el runner único del proceso."""
    return _runner
