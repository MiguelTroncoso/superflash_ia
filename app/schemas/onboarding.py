"""Contratos HTTP del onboarding SSH sin credenciales de respuesta."""

import enum
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OnboardingAuthMethod(enum.StrEnum):
    PRIVATE_KEY = "private_key"
    PASSWORD = "password"


class OnboardingStatus(enum.StrEnum):
    PENDING = "pending"
    CONNECTING = "connecting"
    AUTHENTICATING = "authenticating"
    DISCOVERING = "discovering"
    INSTALLING_EXPORTER = "installing_exporter"
    CONFIGURING_FIREWALL = "configuring_firewall"
    VERIFYING_EXPORTER = "verifying_exporter"
    REGISTERING_INVENTORY = "registering_inventory"
    CONFIGURING_MONITORING = "configuring_monitoring"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLBACK_REQUIRED = "rollback_required"


class OnboardingStep(enum.StrEnum):
    PENDING = "pending"
    CONNECTING = "connecting"
    AUTHENTICATING = "authenticating"
    DISCOVERING = "discovering"
    INSTALLING_EXPORTER = "installing_exporter"
    CONFIGURING_FIREWALL = "configuring_firewall"
    VERIFYING_EXPORTER = "verifying_exporter"
    REGISTERING_INVENTORY = "registering_inventory"
    CONFIGURING_MONITORING = "configuring_monitoring"
    VALIDATING = "validating"


class OnboardingCredentials(BaseModel):
    """Credencial efímera: solo vive durante la solicitud y tarea en memoria."""

    auth_method: OnboardingAuthMethod
    password: str | None = Field(default=None, min_length=1, max_length=4096)
    private_key: str | None = Field(default=None, min_length=1, max_length=20000)

    @model_validator(mode="after")
    def validate_one_credential(self) -> "OnboardingCredentials":
        if self.auth_method is OnboardingAuthMethod.PASSWORD and not self.password:
            raise ValueError("password es obligatoria para autenticación password")
        if self.auth_method is OnboardingAuthMethod.PRIVATE_KEY and not self.private_key:
            raise ValueError("private_key es obligatoria para autenticación por clave")
        if self.auth_method is OnboardingAuthMethod.PASSWORD and self.private_key:
            raise ValueError("private_key no se acepta con autenticación password")
        if self.auth_method is OnboardingAuthMethod.PRIVATE_KEY and self.password:
            raise ValueError("password no se acepta con autenticación por clave")
        return self


class OnboardingStartRequest(OnboardingCredentials):
    """Datos de inventario y acceso para iniciar un onboarding."""

    name: str = Field(min_length=1, max_length=200)
    external_id: str | None = Field(default=None, min_length=1, max_length=100)
    ip: str = Field(min_length=1, max_length=255)
    ssh_port: int = Field(default=22, ge=1, le=65_535)
    ssh_username: str = Field(min_length=1, max_length=120)
    prometheus_url: str | None = Field(default=None, max_length=500)
    role: str = Field(default="other", max_length=20)
    provider: str | None = Field(default=None, max_length=120)
    datacenter: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    server_type: str | None = Field(default=None, max_length=80)
    network_interface: str | None = Field(
        default=None, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$"
    )
    physical_capacity_mbps: float | None = Field(default=None, ge=0)
    operational_target_mbps: float | None = Field(default=None, ge=0)
    recommended_max_mbps: float | None = Field(default=None, ge=0)
    minimum_reserve_mbps: float | None = Field(default=None, ge=0)
    monthly_cost: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    next_payment_date: date | None = None
    auto_renew: bool = False
    notes: str | None = Field(default=None, max_length=2000)


class OnboardingRetryRequest(OnboardingCredentials):
    """Credencial reingresada para reanudar sin persistirla."""


class OnboardingDiagnosisRead(BaseModel):
    """Resultado sanitizado; nunca contiene stdout, URL privada o secretos."""

    status: str
    node_exporter: str
    prometheus: str
    firewall: str
    network: str
    latency_ms: float | None
    last_sample: str | None
    errors: list[str]


class OnboardingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    server_id: int
    status: OnboardingStatus
    current_step: str
    progress_percent: int
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    last_error_code: str | None
    last_error_message_sanitized: str | None
    retry_count: int
    last_successful_step: str | None
    created_by: str
    auth_method: OnboardingAuthMethod
    ssh_port: int
    ssh_username: str
    cancel_requested: bool
    created_at: datetime
    updated_at: datetime


class OnboardingAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    onboarding_id: int
    server_id: int
    actor: str
    event: str
    step: str | None
    success: bool
    detail_sanitized: str | None
    created_at: datetime


class InventorySnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    server_id: int
    captured_at: datetime
    source: str
    fingerprint: str
    inventory: dict[str, object]
