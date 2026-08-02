"""Modelo persistente de alertas derivadas de métricas."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.server import BigIntPK


class AlertSeverity(enum.StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(enum.StrEnum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Alert(Base):
    """Alerta persistida con ciclo de vida operativo."""

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_server_status", "server_id", "status"),
        Index("ix_alerts_status_last_seen_at", "status", "last_seen_at"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(
            AlertSeverity,
            native_enum=False,
            length=20,
            values_callable=lambda e: [member.value for member in e],
        )
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(
            AlertStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [member.value for member in e],
        ),
        default=AlertStatus.ACTIVE,
    )
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    server_name: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(String(1000))
    value: Mapped[float | None] = mapped_column(Float)
    threshold: Mapped[float | None] = mapped_column(Float)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
