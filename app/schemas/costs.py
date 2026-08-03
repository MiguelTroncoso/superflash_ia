"""Contratos financieros sin secretos ni datos de pago sensibles."""

from datetime import date, datetime

from pydantic import BaseModel

from app.models.intelligence import BillingFrequency, PaymentStatus


class CostProfileRead(BaseModel):
    """Coste operativo informativo asociado a un servidor."""

    id: int
    server_id: int
    server_name: str
    monthly_cost: float
    currency: str
    billing_frequency: BillingFrequency
    next_payment_date: date | None
    provider: str | None
    auto_renew: bool
    payment_status: PaymentStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime


class UpcomingPaymentRead(BaseModel):
    """Próximo vencimiento de un perfil financiero."""

    server_id: int
    server_name: str
    amount: float
    currency: str
    next_payment_date: date
    payment_status: PaymentStatus
    days_until_due: int
    auto_renew: bool


class CostsSummaryRead(BaseModel):
    """Resumen de costes mensuales y proyección anual."""

    generated_at: datetime
    monthly_total: float
    annual_projected: float
    average_per_server: float | None
    profiled_server_count: int
    missing_profile_count: int
    profiles: list[CostProfileRead]
    upcoming: list[UpcomingPaymentRead]
