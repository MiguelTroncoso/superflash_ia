"""Lock distribuido de recolección basado en advisory locks de PostgreSQL.

En PostgreSQL, el lock se toma con ``pg_try_advisory_lock`` sobre una
conexión dedicada que se mantiene abierta durante toda la recolección;
si el proceso muere, la conexión se cierra y PostgreSQL libera el lock
automáticamente (sin locks huérfanos). En cualquier otro dialecto
(SQLite en tests) el lock distribuido es un no-op: la exclusión dentro
del proceso la garantiza el lock de hilo de ``CollectionRunner``.
"""

import logging

from sqlalchemy import Connection, Engine, text

logger = logging.getLogger(__name__)

# Clave fija del advisory lock de recolección (arbitraria, propia del
# proyecto; debe ser la misma en todas las instancias).
ADVISORY_LOCK_KEY = 815_512_001


class DistributedCollectionLock:
    """Exclusión mutua de recolección entre instancias de la API."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._connection: Connection | None = None
        self._is_postgres = engine.dialect.name == "postgresql"

    def try_acquire(self) -> bool:
        """Intenta tomar el lock sin bloquear; True si se obtuvo.

        Fuera de PostgreSQL devuelve siempre True (fallback: el lock de
        hilo del runner cubre el despliegue de proceso único).
        """
        if not self._is_postgres:
            return True
        connection = self._engine.connect()
        try:
            acquired = connection.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY}
            ).scalar()
        except Exception:
            connection.close()
            raise
        if acquired:
            self._connection = connection
            return True
        connection.close()
        logger.info("advisory lock ocupado: otra instancia está recolectando")
        return False

    def release(self) -> None:
        """Libera el lock y cierra la conexión dedicada (idempotente)."""
        if self._connection is None:
            return
        try:
            self._connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY}
            )
        except Exception:
            logger.exception("fallo liberando el advisory lock (la conexión lo liberará)")
        finally:
            self._connection.close()
            self._connection = None
