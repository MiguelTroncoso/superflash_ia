"""Modelo ORM del historial de ejecuciones de recolección."""

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.server import BigIntPK


class CollectionRunStatus(enum.StrEnum):
    """Estado de una ejecución de recolección."""

    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class CollectionTrigger(enum.StrEnum):
    """Origen que disparó la ejecución."""

    MANUAL = "manual"
    SCHEDULER = "scheduler"


class CollectionRun(Base):
    """Registro persistente de cada pasada de recolección.

    Se inserta al iniciar (estado ``running``) y se completa al terminar,
    de modo que cualquier instancia de la API puede consultar el estado
    real aunque la recolección corra en otro proceso.
    """

    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # Última señal de vida de una ejecución activa. Una fila "running" solo
    # se considera realmente en curso si su heartbeat no superó el timeout.
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(100))
    status: Mapped[CollectionRunStatus] = mapped_column(
        Enum(
            CollectionRunStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [member.value for member in e],
        )
    )
    triggered_by: Mapped[CollectionTrigger] = mapped_column(
        Enum(
            CollectionTrigger,
            native_enum=False,
            length=20,
            values_callable=lambda e: [member.value for member in e],
        )
    )
    servers_synced: Mapped[int] = mapped_column(Integer, default=0)
    channels_synced: Mapped[int] = mapped_column(Integer, default=0)
    server_metrics_inserted: Mapped[int] = mapped_column(Integer, default=0)
    server_metrics_skipped: Mapped[int] = mapped_column(Integer, default=0)
    channel_metrics_inserted: Mapped[int] = mapped_column(Integer, default=0)
    channel_metrics_skipped: Mapped[int] = mapped_column(Integer, default=0)
    channels_created: Mapped[int] = mapped_column(Integer, default=0)
    channels_updated: Mapped[int] = mapped_column(Integer, default=0)
    channels_reactivated: Mapped[int] = mapped_column(Integer, default=0)
    channels_deactivated: Mapped[int] = mapped_column(Integer, default=0)
    channels_archived: Mapped[int] = mapped_column(Integer, default=0)
    channels_unchanged: Mapped[int] = mapped_column(Integer, default=0)
    channels_failed: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[str]] = mapped_column(JSON, default=list)
