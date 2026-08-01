"""Persistencia de alertas y su ciclo de vida."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertStatus


class AlertRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, alert_id: int) -> Alert | None:
        return self._session.get(Alert, alert_id)

    def get_by_fingerprint(self, fingerprint: str) -> Alert | None:
        stmt = select(Alert).where(Alert.fingerprint == fingerprint)
        return self._session.scalars(stmt).first()

    def list_current(self) -> list[Alert]:
        stmt = (
            select(Alert)
            .where(Alert.status != AlertStatus.RESOLVED)
            .order_by(Alert.last_seen_at.desc(), Alert.id.desc())
        )
        return list(self._session.scalars(stmt))

    def create(self, fields: dict[str, object]) -> Alert:
        alert = Alert(**fields)
        self._session.add(alert)
        self._session.flush()
        return alert
