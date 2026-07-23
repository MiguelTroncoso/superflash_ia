"""Dependencias y utilidades compartidas por los endpoints."""

from datetime import UTC, datetime

from app.database.session import get_db

__all__ = ["get_db", "to_utc"]


def to_utc(value: datetime | None) -> datetime | None:
    """Normaliza un datetime de query param a UTC.

    Los valores sin zona horaria se interpretan como UTC para que las
    comparaciones contra ``collected_at`` (siempre almacenado en UTC)
    sean consistentes en cualquier backend.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
