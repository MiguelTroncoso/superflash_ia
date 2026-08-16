"""Contratos HTTP del onboarding SSH sin credenciales de respuesta."""

import enum
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.server import ServerProfile


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

    auth_method: OnboardingAuthMethod = OnboardingAuthMethod.PASSWORD
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


class OnboardingDiscoveryRequest(OnboardingCredentials):
    """Discovery efímero; no crea ni modifica un servidor."""

    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=22, ge=1, le=65_535)
    username: str = Field(min_length=1, max_length=120)
    host_key_fingerprint: str | None = Field(default=None, max_length=100)
    confirm_host_key: bool = False


class OnboardingTestSSHRequest(OnboardingDiscoveryRequest):
    """Read-only connection test; it never installs or changes remote state."""


class OnboardingDiscoveryRead(BaseModel):
    """Resultado sanitizado de auto discovery."""

    reachable: bool
    authentication_ok: bool
    privilege_ok: bool
    discovered_inventory: dict[str, object] | None
    host_key_fingerprint: str | None
    host_key_status: str
    detected_firewall: str
    detected_interface: str | None
    link_speed_mbps: int | None
    exporter_status: str
    exporter_version: str | None
    port_9100_status: str
    systemd_available: bool
    warnings: list[str]
    blocking_errors: list[str]
    error_code: str | None = None
    error_message: str | None = None
    probable_cause: str | None = None


class OnboardingTestSSHRead(BaseModel):
    """Sanitized result of the independent SSH preflight."""

    reachable: bool
    authentication_ok: bool
    privilege_ok: bool
    temp_write_ok: bool
    host_key_fingerprint: str | None
    host_key_status: str
    hostname: str | None
    os: str | None
    os_version: str | None
    architecture: str | None
    interfaces: list[dict[str, object]]
    discovered_inventory: dict[str, object] | None
    error_code: str | None = None
    error_message: str | None = None
    probable_cause: str | None = None


class OnboardingHealthRead(BaseModel):
    """Estado consolidado sin requerir reingresar una contraseña temporal."""

    onboarding_status: str
    ssh: str
    privilege: str
    node_exporter: str
    exporter_version: str | None
    firewall: str
    prometheus: str
    prometheus_target_status: str | None = None
    inventory: str
    network_interface: str | None
    metrics_available: bool
    last_scrape: datetime | None
    scrape_age_seconds: int | None
    freshness: str
    latency_ms: float | None
    overall_status: str


class MaintenanceAction(enum.StrEnum):
    DIAGNOSE = "diagnose"
    REPAIR = "repair"
    UPDATE = "update"
    REINSTALL = "reinstall"


class MaintenanceActionRead(BaseModel):
    action: MaintenanceAction
    status: str
    message: str
    exporter_status: str
    exporter_version: str | None


class MaintenanceRequest(OnboardingCredentials):
    """Credencial efímera y versión cerrada para una acción administrada."""

    target_version: str | None = Field(
        default=None, min_length=1, max_length=20, pattern=r"^v?[0-9]+(?:\.[0-9]+){1,3}$"
    )


class OnboardingStartRequest(OnboardingCredentials):
    """Datos de inventario y acceso para iniciar un onboarding."""

    name: str = Field(min_length=1, max_length=200)
    external_id: str | None = Field(default=None, min_length=1, max_length=100)
    ip: str = Field(min_length=1, max_length=255)
    ssh_port: int = Field(default=22, ge=1, le=65_535)
    ssh_username: str = Field(min_length=1, max_length=120)
    host_key_fingerprint: str = Field(min_length=8, max_length=100)
    prometheus_url: str | None = Field(default=None, max_length=500)
    role: str = Field(default="other", max_length=20)
    provider: str | None = Field(default=None, max_length=120)
    datacenter: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    server_type: str | None = Field(default=None, max_length=80)
    server_profile: ServerProfile = ServerProfile.REPLACEABLE
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
    prometheus_target_status: str | None = None
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
