"""Ejecución serializada de recolecciones con historial persistente.

Exclusión mutua en dos niveles:

1. Lock de hilo no bloqueante: impide dos recolecciones en el mismo
   proceso (válido también en SQLite/tests).
2. Advisory lock de PostgreSQL (``DistributedCollectionLock``): impide
   dos recolecciones simultáneas entre instancias distintas de la API.
   Fuera de PostgreSQL es un no-op.

Cada ejecución queda registrada en la tabla ``collection_runs``: se
inserta al iniciar (estado ``running``) y se completa al terminar con
duración, contadores y errores, de modo que el estado sobrevive al
proceso y es visible desde cualquier instancia.
"""

import logging
import threading
from datetime import UTC, datetime

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.adapters.base import MonitoringSourceAdapter
from app.collectors.collection import CollectionService
from app.collectors.lock import DistributedCollectionLock
from app.models.collection_run import CollectionTrigger
from app.repositories.collection_run_repository import CollectionRunRepository
from app.schemas.collection import CollectionResult

logger = logging.getLogger(__name__)


class CollectionAlreadyRunningError(RuntimeError):
    """Se intentó iniciar una recolección mientras otra estaba en curso."""


class CollectionRunner:
    """Serializa las recolecciones y persiste su historial."""

    def __init__(self) -> None:
        self._thread_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._running_since: datetime | None = None

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

    def run(
        self,
        session: Session,
        adapter: MonitoringSourceAdapter,
        triggered_by: CollectionTrigger = CollectionTrigger.MANUAL,
    ) -> CollectionResult:
        """Ejecuta una recolección si no hay otra en curso.

        Raises:
            CollectionAlreadyRunningError: Si otra recolección está
                activa en este proceso o en otra instancia (advisory
                lock de PostgreSQL ocupado).
        """
        if not self._thread_lock.acquire(blocking=False):
            raise CollectionAlreadyRunningError("ya hay una recolección en curso en este proceso")

        bind = session.get_bind()
        assert isinstance(bind, Engine)
        distributed_lock = DistributedCollectionLock(bind)
        try:
            if not distributed_lock.try_acquire():
                raise CollectionAlreadyRunningError(
                    "otra instancia está ejecutando una recolección"
                )
            return self._run_locked(session, adapter, triggered_by)
        finally:
            distributed_lock.release()
            self._thread_lock.release()

    def _run_locked(
        self,
        session: Session,
        adapter: MonitoringSourceAdapter,
        triggered_by: CollectionTrigger,
    ) -> CollectionResult:
        """Ejecuta la recolección con los locks ya tomados."""
        started_at = datetime.now(UTC)
        with self._state_lock:
            self._running_since = started_at

        runs = CollectionRunRepository(session)
        run_row = runs.start(
            source=adapter.source_name, started_at=started_at, triggered_by=triggered_by
        )
        session.commit()

        try:
            result = CollectionService(session, adapter).run()
            runs.finish_success(run_row, result, finished_at=datetime.now(UTC))
            session.commit()
            return result
        except Exception as exc:
            session.rollback()
            runs.finish_error(
                run_row,
                error=f"{type(exc).__name__}: {exc}",
                finished_at=datetime.now(UTC),
            )
            session.commit()
            raise
        finally:
            with self._state_lock:
                self._running_since = None

    def reset(self) -> None:
        """Limpia el estado en memoria (uso exclusivo en tests)."""
        with self._state_lock:
            self._running_since = None


_runner = CollectionRunner()


def get_collection_runner() -> CollectionRunner:
    """Devuelve el runner único del proceso."""
    return _runner
