"""Dependencias y utilidades compartidas por los endpoints."""

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.timeutils import to_utc
from app.database.session import get_db

__all__ = ["get_db", "require_api_key", "to_utc"]


def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """Exige la clave de API en la cabecera ``X-API-Key``.

    Protege todos los endpoints ``/api/v1`` (``/health`` queda público).
    Política *fail-closed*: si ``API_KEY`` no está configurada en el
    entorno, la API se niega a operar (503) en lugar de quedar abierta.
    La clave nunca se registra en logs ni se incluye en errores.
    """
    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API deshabilitada: API_KEY no está configurada",
        )
    if x_api_key is None or not secrets.compare_digest(
        x_api_key.encode(), settings.api_key.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clave de API ausente o inválida",
        )
