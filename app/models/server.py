"""Modelos ORM de servidores y sus métricas históricas."""

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
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

# En SQLite (tests) un BIGINT no autoincrementa como clave primaria;
# esta variante mantiene BIGINT en PostgreSQL e INTEGER en SQLite.
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


class ServerRole(enum.StrEnum):
    """Rol funcional de un servidor dentro de la infraestructura."""

    MAIN = "main"
    LIVE = "live"
    VOD = "vod"
    OTHER = "other"


class Server(Base):
    """Servidor físico o virtual monitoreado."""

    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    hostname: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[ServerRole] = mapped_column(
        Enum(
            ServerRole,
            native_enum=False,
            length=20,
            values_callable=lambda e: [member.value for member in e],
        )
    )
    network_capacity_mbps: Mapped[float | None] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    metrics: Mapped[list["ServerMetric"]] = relationship(
        back_populates="server", cascade="all, delete-orphan", passive_deletes=True
    )


class ServerMetric(Base):
    """Muestra puntual de métricas de un servidor (cadencia prevista: 5 min)."""

    __tablename__ = "server_metrics"
    __table_args__ = (
        UniqueConstraint("server_id", "collected_at", name="uq_server_metrics_server_collected"),
        Index("ix_server_metrics_server_collected", "server_id", "collected_at"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cpu_percent: Mapped[float] = mapped_column(Float)
    memory_percent: Mapped[float] = mapped_column(Float)
    # Solo lo entregan fuentes de infraestructura granulares (composite).
    disk_percent: Mapped[float | None] = mapped_column(Float)
    input_mbps: Mapped[float] = mapped_column(Float)
    output_mbps: Mapped[float] = mapped_column(Float)
    active_connections: Mapped[int] = mapped_column(Integer)
    active_streams: Mapped[int] = mapped_column(Integer)
    uptime_seconds: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(50))

    server: Mapped[Server] = relationship(back_populates="metrics")
