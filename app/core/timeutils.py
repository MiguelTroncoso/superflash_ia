"""Utilidades de tiempo compartidas por API y servicios.

Todos los timestamps de la plataforma se manejan en UTC. SQLite (usado
en tests) devuelve datetimes sin zona horaria; estas utilidades los
normalizan para poder compararlos con instantes aware.
"""

from datetime import UTC, datetime


def to_utc(value: datetime | None) -> datetime | None:
    """Normaliza un datetime opcional a UTC (naive se asume UTC)."""
    if value is None:
        return None
    return ensure_utc(value)


def ensure_utc(value: datetime) -> datetime:
    """Devuelve el datetime en UTC; si es naive se asume que ya está en UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
