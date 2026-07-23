"""Esquema de la respuesta del healthcheck."""

from typing import Literal

from pydantic import BaseModel


class HealthRead(BaseModel):
    """Estado de la aplicación y de sus dependencias."""

    status: Literal["ok", "degraded"]
    database: Literal["ok", "error"]
    version: str
