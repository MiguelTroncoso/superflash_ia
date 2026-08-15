"""Persistencia del proceso seguro de incorporación SSH."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.server import BigIntPK

if TYPE_CHECKING:
    from app.models.server import Server


class ServerInventorySnapshot(Base):
    """Snapshot técnico deduplicado por huella, nunca contiene credenciales."""

    __tablename__ = "server_inventory_snapshots"
    __table_args__ = (Index("ix_server_inventory_server_captured", "server_id", "captured_at"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="ssh_onboarding")
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    inventory: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)

    server: Mapped[Server] = relationship(back_populates="inventory_snapshots")


class ServerOnboarding(Base):
    """Estado durable de un onboarding; no persiste passwords ni claves privadas."""

    __tablename__ = "server_onboardings"
    __table_args__ = (
        Index("ix_server_onboardings_server_created", "server_id", "created_at"),
        Index("ix_server_onboardings_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    current_step: Mapped[str] = mapped_column(String(60), nullable=False, default="pending")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error_message_sanitized: Mapped[str | None] = mapped_column(String(500))
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_successful_step: Mapped[str | None] = mapped_column(String(60))
    created_by: Mapped[str] = mapped_column(String(120), nullable=False, default="api-key-operator")
    auth_method: Mapped[str] = mapped_column(String(20), nullable=False)
    ssh_port: Mapped[int] = mapped_column(Integer, nullable=False, default=22)
    ssh_username: Mapped[str] = mapped_column(String(120), nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    server: Mapped[Server] = relationship(back_populates="onboardings")
    audit_events: Mapped[list[OnboardingAuditEvent]] = relationship(
        back_populates="onboarding", cascade="all, delete-orphan", passive_deletes=True
    )


class OnboardingAuditEvent(Base):
    """Auditoría operacional sin stdout, stderr ni material secreto."""

    __tablename__ = "onboarding_audit_events"
    __table_args__ = (
        Index("ix_onboarding_audit_onboarding_created", "onboarding_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    onboarding_id: Mapped[int] = mapped_column(
        ForeignKey("server_onboardings.id", ondelete="CASCADE"), index=True
    )
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    event: Mapped[str] = mapped_column(String(80), nullable=False)
    step: Mapped[str | None] = mapped_column(String(60))
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    detail_sanitized: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    onboarding: Mapped[ServerOnboarding] = relationship(back_populates="audit_events")
