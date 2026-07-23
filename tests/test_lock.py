"""Tests del lock distribuido de recolección (advisory lock de PostgreSQL)."""

import os

import pytest
from sqlalchemy import create_engine

from app.collectors.lock import DistributedCollectionLock

# URL de un PostgreSQL de pruebas. Si no está definida, los tests que
# requieren PostgreSQL real se omiten (CI los ejecuta en el job con el
# servicio de PostgreSQL).
PG_URL = os.environ.get("SUPERFLASH_TEST_PG_URL")


def test_non_postgres_fallback_always_acquires(engine):
    """Fuera de PostgreSQL el lock distribuido es un no-op que siempre concede.

    La exclusión en ese caso la garantiza el lock de hilo del runner
    (cubierto en test_collection_control).
    """
    lock = DistributedCollectionLock(engine)
    assert lock.try_acquire() is True
    other = DistributedCollectionLock(engine)
    assert other.try_acquire() is True
    lock.release()
    other.release()


@pytest.mark.skipif(PG_URL is None, reason="requiere PostgreSQL (SUPERFLASH_TEST_PG_URL)")
def test_postgres_advisory_lock_mutual_exclusion():
    """En PostgreSQL, el segundo intento falla mientras el primero retiene."""
    assert PG_URL is not None
    engine = create_engine(PG_URL)
    try:
        first = DistributedCollectionLock(engine)
        second = DistributedCollectionLock(engine)

        assert first.try_acquire() is True
        assert second.try_acquire() is False, "el lock debe estar ocupado"

        first.release()
        assert second.try_acquire() is True, "liberado el primero, el segundo entra"
        second.release()
    finally:
        engine.dispose()


@pytest.mark.skipif(PG_URL is None, reason="requiere PostgreSQL (SUPERFLASH_TEST_PG_URL)")
def test_postgres_advisory_lock_release_is_idempotent():
    """Liberar dos veces no falla ni afecta a adquisiciones posteriores."""
    assert PG_URL is not None
    engine = create_engine(PG_URL)
    try:
        lock = DistributedCollectionLock(engine)
        assert lock.try_acquire() is True
        lock.release()
        lock.release()
        assert lock.try_acquire() is True
        lock.release()
    finally:
        engine.dispose()
