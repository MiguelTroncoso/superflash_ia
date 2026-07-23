"""Dependencias y utilidades compartidas por los endpoints."""

import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings
from app.database.session import get_db

__all__ = ["get_db", "require_collection_api_key", "to_utc"]


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


def require_collection_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """Exige la clave interna de recolección en la cabecera ``X-API-Key``.

    Política *fail-closed*: si ``COLLECTION_API_KEY`` no está configurada
    en el entorno, el endpoint se niega a operar (503) en lugar de quedar
    abierto. La clave nunca se registra en logs ni se incluye en errores.
    """
    if not settings.collection_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Endpoint interno deshabilitado: COLLECTION_API_KEY no está configurada",
        )
    if x_api_key is None or not secrets.compare_digest(
        x_api_key.encode(), settings.collection_api_key.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clave de API ausente o inválida",
        )
