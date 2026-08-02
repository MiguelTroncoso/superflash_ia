"""Modelos ORM de canales y sus métricas históricas."""

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


class Channel(Base):
    """Canal de contenido distribuido por la infraestructura."""

    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    current_server_id: Mapped[int | None] = mapped_column(
        ForeignKey("servers.id", ondelete="SET NULL"), index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    current_server: Mapped[Server | None] = relationship()
    metrics: Mapped[list["ChannelMetric"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan", passive_deletes=True
    )


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
    server: Mapped[Server | None] = relationship()
