"""Base declarativa de SQLAlchemy con convención de nombres estable.

La convención de nombres garantiza que índices y constraints tengan
nombres deterministas, lo que hace las migraciones de Alembic portables
y reversibles.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Clase base para todos los modelos ORM del proyecto."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
