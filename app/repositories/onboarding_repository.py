"""Persistencia del estado y auditoría de onboarding SSH."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.onboarding import OnboardingAuditEvent, ServerInventorySnapshot, ServerOnboarding


class OnboardingRepository:
    """Consultas pequeñas y explícitas para no mezclar secretos con ORM."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, onboarding_id: int) -> ServerOnboarding | None:
        return self._session.get(ServerOnboarding, onboarding_id)

    def latest_for_server(self, server_id: int) -> ServerOnboarding | None:
        stmt = (
            select(ServerOnboarding)
            .where(ServerOnboarding.server_id == server_id)
            .order_by(ServerOnboarding.created_at.desc(), ServerOnboarding.id.desc())
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    def active_for_server(self, server_id: int) -> ServerOnboarding | None:
        stmt = (
            select(ServerOnboarding)
            .where(
                ServerOnboarding.server_id == server_id,
                ServerOnboarding.status.in_(
                    [
                        "pending",
                        "connecting",
                        "authenticating",
                        "discovering",
                        "installing_exporter",
                        "configuring_firewall",
                        "verifying_exporter",
                        "registering_inventory",
                        "configuring_monitoring",
                        "validating",
                    ]
                ),
            )
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    def create(self, onboarding: ServerOnboarding) -> ServerOnboarding:
        self._session.add(onboarding)
        self._session.flush()
        return onboarding

    def add_audit(self, event: OnboardingAuditEvent) -> None:
        self._session.add(event)
        self._session.flush()

    def audit_for(self, onboarding_id: int) -> list[OnboardingAuditEvent]:
        stmt = (
            select(OnboardingAuditEvent)
            .where(OnboardingAuditEvent.onboarding_id == onboarding_id)
            .order_by(OnboardingAuditEvent.created_at, OnboardingAuditEvent.id)
        )
        return list(self._session.scalars(stmt))

    def add_inventory_snapshot_if_changed(
        self,
        *,
        server_id: int,
        captured_at: datetime,
        fingerprint: str,
        inventory: dict[str, object],
    ) -> ServerInventorySnapshot:
        stmt = select(ServerInventorySnapshot).where(
            ServerInventorySnapshot.server_id == server_id,
            ServerInventorySnapshot.fingerprint == fingerprint,
        )
        existing = self._session.scalars(stmt).first()
        if existing is not None:
            return existing
        snapshot = ServerInventorySnapshot(
            server_id=server_id,
            captured_at=captured_at,
            fingerprint=fingerprint,
            inventory=inventory,
        )
        self._session.add(snapshot)
        self._session.flush()
        return snapshot
