"""Motor de base de datos y fábrica de sesiones.

El motor se crea de forma perezosa a partir de la configuración, de modo
que los tests puedan sustituirlo sin conectarse a PostgreSQL.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Crea (una sola vez) el motor de SQLAlchemy según la configuración."""
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Devuelve la fábrica de sesiones ligada al motor de la aplicación."""
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: entrega una sesión y la cierra al terminar."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
