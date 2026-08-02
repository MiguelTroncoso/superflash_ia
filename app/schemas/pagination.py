"""Contratos compartidos para listados paginados."""

from pydantic import BaseModel, Field


class PageMetadata(BaseModel):
    """Metadatos estables de una página de resultados."""

    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)
