"""Resumen financiero determinista para planificación."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.intelligence import PaymentStatus, ServerCostProfile
from app.models.server import Server
from app.repositories.cost_repository import CostRepository
from app.schemas.costs import CostProfileRead, CostsSummaryRead, UpcomingPaymentRead


def effective_payment_status(
    profile: ServerCostProfile, today: date, due_soon_days: int
) -> PaymentStatus:
    """Calcula estado de vencimiento sin mutar el perfil persistido."""
    if profile.payment_status in {PaymentStatus.PAID, PaymentStatus.CANCELLED}:
        return profile.payment_status
    if profile.next_payment_date is None:
        return profile.payment_status
    if profile.next_payment_date < today:
        return PaymentStatus.OVERDUE
    if profile.next_payment_date <= today + timedelta(days=due_soon_days):
        return PaymentStatus.DUE_SOON
    return profile.payment_status


class CostService:
    """Lee perfiles locales; no procesa credenciales ni pagos."""

    def __init__(self, session: Session) -> None:
        self._repository = CostRepository(session)

    def _profile_rows(self) -> list[tuple[ServerCostProfile, Server]]:
        return self._repository.list_enabled_profiles()

    @staticmethod
    def _read_profiles(rows: list[tuple[ServerCostProfile, Server]]) -> list[CostProfileRead]:
        today = datetime.now(UTC).date()
        return [
            CostProfileRead(
                id=profile.id,
                server_id=profile.server_id,
                server_name=server.name,
                monthly_cost=round(profile.monthly_cost, 2),
                currency=profile.currency,
                billing_frequency=profile.billing_frequency,
                next_payment_date=profile.next_payment_date,
                provider=profile.provider,
                auto_renew=profile.auto_renew,
                payment_status=effective_payment_status(profile, today, 30),
                notes=profile.notes,
                created_at=profile.created_at,
                updated_at=profile.updated_at,
            )
            for profile, server in rows
        ]

    @staticmethod
    def _upcoming_rows(
        rows: list[tuple[ServerCostProfile, Server]], days: int
    ) -> list[UpcomingPaymentRead]:
        today = datetime.now(UTC).date()
        cutoff = today + timedelta(days=days)
        upcoming: list[UpcomingPaymentRead] = []
        for profile, server in rows:
            if profile.next_payment_date is None or profile.next_payment_date > cutoff:
                continue
            status = effective_payment_status(profile, today, days)
            if status == PaymentStatus.CANCELLED:
                continue
            upcoming.append(
                UpcomingPaymentRead(
                    server_id=profile.server_id,
                    server_name=server.name,
                    amount=round(profile.monthly_cost, 2),
                    currency=profile.currency,
                    next_payment_date=profile.next_payment_date,
                    payment_status=status,
                    days_until_due=(profile.next_payment_date - today).days,
                    auto_renew=profile.auto_renew,
                )
            )
        return sorted(upcoming, key=lambda item: (item.next_payment_date, item.server_name))

    def upcoming(self, days: int = 30) -> list[UpcomingPaymentRead]:
        return self._upcoming_rows(self._profile_rows(), days)

    def build(self) -> CostsSummaryRead:
        rows = self._profile_rows()
        profiles = self._read_profiles(rows)
        currencies = {profile.currency for profile in profiles}
        # No FX conversion is inferred. Mixed currencies are reported as
        # insufficiently comparable by exposing no aggregate total.
        comparable = len(currencies) <= 1
        monthly = round(sum(profile.monthly_cost for profile in profiles), 2) if comparable else 0.0
        average = round(monthly / len(profiles), 2) if profiles and comparable else None
        upcoming = self._upcoming_rows(rows, 30)
        return CostsSummaryRead(
            generated_at=datetime.now(UTC),
            monthly_total=monthly,
            annual_projected=round(monthly * 12, 2),
            average_per_server=average,
            profiled_server_count=len(profiles),
            missing_profile_count=max(self._repository.count_enabled_servers() - len(profiles), 0),
            profiles=profiles,
            upcoming=upcoming,
        )
