"""Modelos ORM de canales, eventos, streams y métricas históricas."""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.server import BigIntPK, Server


class ChannelStatus(enum.StrEnum):
    """Estado operativo reportado para un canal en una muestra."""

    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class ChannelType(enum.StrEnum):
    """Clasificación de ciclo de vida para un canal de una fuente."""

    PERMANENT = "permanent"
    EVENT = "event"
    TEMPORARY = "temporary"
    SCHEDULED = "scheduled"
    ARCHIVED = "archived"


class ChannelEvent(Base):
    """Evento concreto al que un canal puede estar asociado."""

    __tablename__ = "channel_events"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_channel_events_source_external"),
        Index("ix_channel_events_source_start", "source_id", "event_start_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(120), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    category_id: Mapped[str | None] = mapped_column(String(100), index=True)
    category_name: Mapped[str | None] = mapped_column(String(100))
    event_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    event_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TechnicalStream(Base):
    """Stream técnico reutilizable entre eventos de distintas fechas."""

    __tablename__ = "technical_streams"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_technical_streams_source_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(120), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    name: Mapped[str | None] = mapped_column(String(200))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class Channel(Base):
    """Canal de contenido distribuido por la infraestructura."""

    __tablename__ = "channels"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_channels_source_external"),
        Index("ix_channels_source_active", "source_id", "active"),
        Index("ix_channels_type_active", "channel_type", "active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(120), default="legacy", index=True)
    external_id: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    category_id: Mapped[str | None] = mapped_column(String(100), index=True)
    channel_type: Mapped[ChannelType] = mapped_column(
        Enum(
            ChannelType,
            native_enum=False,
            length=20,
            values_callable=lambda e: [member.value for member in e],
        ),
        default=ChannelType.PERMANENT,
        index=True,
    )
    event_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    event_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    inactive_since_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_server_id: Mapped[int | None] = mapped_column(
        ForeignKey("servers.id", ondelete="SET NULL"), index=True
    )
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("channel_events.id", ondelete="SET NULL"), index=True
    )
    technical_stream_id: Mapped[int | None] = mapped_column(
        ForeignKey("technical_streams.id", ondelete="SET NULL"), index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    current_server: Mapped[Server | None] = relationship()
    event: Mapped[ChannelEvent | None] = relationship()
    technical_stream: Mapped[TechnicalStream | None] = relationship()
    category_history: Mapped[list["ChannelCategoryHistory"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan", passive_deletes=True
    )
    metrics: Mapped[list["ChannelMetric"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def category_name(self) -> str | None:
        """Nombre de la categoría actual, conservado como ``category`` por compatibilidad."""
        return self.category


class ChannelCategoryHistory(Base):
    """Intervalos históricos de categoría de un canal."""

    __tablename__ = "channel_category_history"
    __table_args__ = (
        Index("ix_channel_category_history_channel_valid_from", "channel_id", "valid_from"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[str] = mapped_column(String(120))
    category_id: Mapped[str | None] = mapped_column(String(100))
    category_name: Mapped[str | None] = mapped_column(String(100))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    channel: Mapped[Channel] = relationship(back_populates="category_history")


class ChannelMetric(Base):
    """Muestra puntual de métricas de un canal (cadencia prevista: 5 min)."""

    __tablename__ = "channel_metrics"
    __table_args__ = (
        UniqueConstraint("channel_id", "collected_at", name="uq_channel_metrics_channel_collected"),
        Index("ix_channel_metrics_channel_collected", "channel_id", "collected_at"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("channel_events.id", ondelete="SET NULL"), index=True
    )
    technical_stream_id: Mapped[int | None] = mapped_column(
        ForeignKey("technical_streams.id", ondelete="SET NULL"), index=True
    )
    server_id: Mapped[int | None] = mapped_column(
        ForeignKey("servers.id", ondelete="SET NULL"), index=True
    )
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    viewers: Mapped[int] = mapped_column(Integer)
    bitrate_mbps: Mapped[float | None] = mapped_column(Float)
    estimated_output_mbps: Mapped[float | None] = mapped_column(Float)
    status: Mapped[ChannelStatus] = mapped_column(
        Enum(
            ChannelStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [member.value for member in e],
        )
    )

    channel: Mapped[Channel] = relationship(back_populates="metrics")
    event: Mapped[ChannelEvent | None] = relationship()
    technical_stream: Mapped[TechnicalStream | None] = relationship()
    server: Mapped[Server | None] = relationship()
