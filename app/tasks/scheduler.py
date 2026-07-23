"""Programador opcional de recolección periódica (in-process).

Deshabilitado por defecto (``SCHEDULER_ENABLED=false``). Cuando se
habilita, ejecuta una recolección cada ``COLLECTION_INTERVAL_SECONDS``
segundos (300 = cinco minutos) reutilizando el mismo
``CollectionRunner`` que el endpoint manual, por lo que nunca puede
solaparse con una recolección disparada a mano: la que llegue segunda
simplemente se omite y queda registrada en el log.

Limitación conocida: es un programador de proceso único. Con varias
réplicas de la API deberá sustituirse por un programador externo (cron,
contenedor dedicado) o un lock distribuido; ver docs/architecture.md.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from app.adapters.base import MonitoringSourceAdapter
from app.collectors.runner import CollectionAlreadyRunningError, CollectionRunner
from app.models.collection_run import CollectionTrigger

logger = logging.getLogger(__name__)


class CollectionScheduler:
    """Dispara recolecciones periódicas dentro del proceso de la API."""

    def __init__(
        self,
        interval_seconds: float,
        session_factory: sessionmaker[Session],
        adapter_factory: Callable[[], MonitoringSourceAdapter],
        runner: CollectionRunner,
    ) -> None:
        self._interval = interval_seconds
        self._session_factory = session_factory
        self._adapter_factory = adapter_factory
        self._runner = runner
        self._task: asyncio.Task[None] | None = None
        self._next_run_at: datetime | None = None

    @property
    def interval_seconds(self) -> float:
        """Intervalo configurado entre recolecciones."""
        return self._interval

    @property
    def next_run_at(self) -> datetime | None:
        """Instante estimado del próximo ciclo, si el scheduler corre."""
        return self._next_run_at

    @property
    def is_active(self) -> bool:
        """Indica si el bucle periódico está en marcha."""
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """Arranca el bucle periódico (idempotente)."""
        if self.is_active:
            return
        self._task = asyncio.get_running_loop().create_task(self._loop())
        logger.info("scheduler iniciado intervalo=%.0fs", self._interval)

    async def stop(self) -> None:
        """Detiene el bucle periódico y espera su cancelación."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._next_run_at = None
        logger.info("scheduler detenido")

    async def _loop(self) -> None:
        """Espera el intervalo y ejecuta una recolección, indefinidamente.

        La primera recolección ocurre un intervalo después del arranque
        (no inmediatamente), para no competir con el proceso de despliegue.
        """
        while True:
            self._next_run_at = datetime.now(UTC) + timedelta(seconds=self._interval)
            await asyncio.sleep(self._interval)
            await asyncio.to_thread(self._collect_once)

    def _collect_once(self) -> None:
        """Una pasada de recolección; nunca propaga excepciones al bucle."""
        session = self._session_factory()
        try:
            self._runner.run(
                session, self._adapter_factory(), triggered_by=CollectionTrigger.SCHEDULER
            )
        except CollectionAlreadyRunningError:
            logger.warning("scheduler: ciclo omitido, ya hay una recolección en curso")
        except Exception:
            logger.exception("scheduler: la recolección periódica falló")
        finally:
            session.close()


_active_scheduler: CollectionScheduler | None = None


def set_active_scheduler(scheduler: CollectionScheduler | None) -> None:
    """Registra (o retira) el scheduler activo del proceso."""
    global _active_scheduler
    _active_scheduler = scheduler


def get_active_scheduler() -> CollectionScheduler | None:
    """Devuelve el scheduler activo, si la aplicación lo habilitó."""
    return _active_scheduler
