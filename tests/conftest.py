"""Fixtures compartidas: base de datos SQLite en memoria y cliente HTTP.

Los tests no requieren PostgreSQL: el esquema es portable y se crea con
``Base.metadata.create_all`` sobre SQLite. Las mismas consultas corren
en PostgreSQL en despliegue (tipos y constraints portables).
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - registra todas las tablas en Base.metadata
from app.database.base import Base
from app.database.session import get_db
from app.main import app as fastapi_app

# Instante fijo para tests deterministas (se trunca al minuto: 12:34:00Z).
FIXED_NOW = datetime(2026, 7, 23, 12, 34, 56, tzinfo=UTC)


@pytest.fixture()
def engine() -> Iterator[Engine]:
    """Motor SQLite en memoria compartido entre sesión y cliente HTTP."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # pysqlite no maneja bien los SAVEPOINT con su gestión implícita de
    # transacciones; esta receta (documentada por SQLAlchemy) lo corrige.
    @event.listens_for(engine, "connect")
    def _set_sqlite_isolation(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin_sqlite(conn) -> None:  # type: ignore[no-untyped-def]
        conn.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Fábrica de sesiones ligada al motor de tests."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Sesión de base de datos para preparar o inspeccionar datos."""
    db = session_factory()
    yield db
    db.close()


@pytest.fixture()
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    """Cliente HTTP con la dependencia de base de datos redirigida a SQLite."""

    def _override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
