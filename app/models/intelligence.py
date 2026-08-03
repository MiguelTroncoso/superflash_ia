"""Modelos financieros y de historial del motor de inteligencia."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, Float, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.server import Server


class BillingFrequency(enum.StrEnum):
    """Frecuencia con que se factura un recurso."""

    MONTHLY = "monthly"
    ANNUAL = "annual"
    CUSTOM = "custom"


class PaymentStatus(enum.StrEnum):
    """Estado informativo del próximo pago."""

    PAID = "paid"
    PENDING = "pending"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class ServerCostProfile(Base):
    """Perfil financiero separado de las métricas técnicas del servidor."""

    __tablename__ = "server_cost_profiles"
    __table_args__ = (
        Index("ix_server_cost_profiles_next_payment", "next_payment_date"),
        Index("ix_server_cost_profiles_payment_status", "payment_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(
        ForeignKey("servers.id", ondelete="CASCADE"), unique=True, index=True
    )
    monthly_cost: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    billing_frequency: Mapped[BillingFrequency] = mapped_column(
        Enum(
            BillingFrequency,
            native_enum=False,
            length=20,
            values_callable=lambda e: [member.value for member in e],
        ),
        default=BillingFrequency.MONTHLY,
    )
    next_payment_date: Mapped[date | None] = mapped_column(Date)
    provider: Mapped[str | None] = mapped_column(String(120))
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [member.value for member in e],
        ),
        default=PaymentStatus.PENDING,
    )
    notes: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    server: Mapped[Server] = relationship(back_populates="cost_profile")


class Simulation(Base):
    """Historial local de una simulación informativa."""

    __tablename__ = "simulations"
    __table_args__ = (Index("ix_simulations_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
