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
from app.collectors.runner import get_collection_runner
from app.core.config import Settings, get_settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app as fastapi_app

# Instante fijo para tests deterministas (se trunca al minuto: 12:34:00Z).
FIXED_NOW = datetime(2026, 7, 23, 12, 34, 56, tzinfo=UTC)

# Clave usada por los tests para el endpoint interno de recolección.
TEST_API_KEY = "test-api-key"


def make_test_settings(**overrides: object) -> Settings:
    """Settings aislados del entorno y del archivo .env local."""
    defaults: dict[str, object] = {"api_key": TEST_API_KEY}
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _reset_collection_runner() -> Iterator[None]:
    """Limpia el estado del runner (singleton de proceso) entre tests."""
    get_collection_runner().reset()
    yield
    get_collection_runner().reset()


def _configure_sqlite_savepoints(engine: Engine) -> None:
    """Receta de SQLAlchemy: pysqlite no maneja bien los SAVEPOINT con su
    gestión implícita de transacciones; esto lo corrige."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_isolation(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin_sqlite(conn) -> None:  # type: ignore[no-untyped-def]
        conn.exec_driver_sql("BEGIN")


@pytest.fixture()
def engine() -> Iterator[Engine]:
    """Motor SQLite en memoria compartido entre sesión y cliente HTTP."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _configure_sqlite_savepoints(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def file_engine(tmp_path) -> Iterator[Engine]:
    """Motor SQLite en archivo: una conexión por hilo, sin interferencias.

    Necesario en tests que consultan la base desde un hilo mientras otro
    ejecuta una recolección (el StaticPool en memoria comparte una única
    conexión y mezclaría las transacciones).
    """
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    _configure_sqlite_savepoints(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def file_session_factory(file_engine: Engine) -> sessionmaker[Session]:
    """Fábrica de sesiones sobre el motor SQLite en archivo."""
    return sessionmaker(bind=file_engine, autoflush=False, expire_on_commit=False)


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


def _install_overrides(session_factory: sessionmaker[Session]) -> None:
    def _override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    test_settings = make_test_settings()
    fastapi_app.dependency_overrides[get_db] = _override_get_db
    fastapi_app.dependency_overrides[get_settings] = lambda: test_settings


@pytest.fixture()
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    """Cliente HTTP autenticado (X-API-Key por defecto) sobre SQLite."""
    _install_overrides(session_factory)
    with TestClient(fastapi_app, headers={"X-API-Key": TEST_API_KEY}) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def anon_client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    """Cliente HTTP sin credenciales, para probar la autenticación."""
    _install_overrides(session_factory)
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
