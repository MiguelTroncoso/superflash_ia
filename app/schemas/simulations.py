"""Contratos de simulaciones deterministas y no destructivas."""

import enum
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class LoadUnitKind(enum.StrEnum):
    """Unidad de carga genérica para el motor de distribución."""

    CHANNEL = "channel"
    STREAM = "stream"
    CATEGORY = "category"
    GROUP = "group"
    EVENT = "event"
    TRAFFIC_BLOCK = "traffic_block"
    SERVER_AGGREGATE = "server_aggregate"


class SimulationRisk(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    INSUFFICIENT_DATA = "insufficient_data"


class SimulationDataQuality(enum.StrEnum):
    OBSERVED = "observed"
    SIMULATED = "simulated"
    INSUFFICIENT_DATA = "insufficient_data"


class SimulationLoadUnit(BaseModel):
    """Carga que el motor puede asignar sin conocer el tipo de stream."""

    id: str = Field(min_length=1, max_length=160)
    load_mbps: float = Field(ge=0, le=1_000_000)
    kind: LoadUnitKind = LoadUnitKind.CHANNEL
    current_server_id: int | None = Field(default=None, ge=1)
    label: str | None = Field(default=None, max_length=200)


class SimulationServerOverride(BaseModel):
    """Cambios virtuales aplicados solo al cálculo de una simulación."""

    server_id: int = Field(ge=1)
    physical_capacity_mbps: float | None = Field(default=None, gt=0)
    operational_limit_mbps: float | None = Field(default=None, gt=0)
    recommended_limit_mbps: float | None = Field(default=None, gt=0)
    minimum_reserve_mbps: float | None = Field(default=None, ge=0)
    monthly_cost: float | None = Field(default=None, ge=0)


class VirtualServerInput(BaseModel):
    """Servidor hipotético que no se persiste en el inventario."""

    key: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=200)
    physical_capacity_mbps: float = Field(gt=0)
    operational_limit_mbps: float | None = Field(default=None, gt=0)
    recommended_limit_mbps: float | None = Field(default=None, gt=0)
    minimum_reserve_mbps: float = Field(default=0, ge=0)
    monthly_cost: float | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    provider: str | None = Field(default=None, max_length=120)


class SimulationRequest(BaseModel):
    """Entrada de una simulación informativa."""

    name: str = Field(default="Untitled simulation", min_length=1, max_length=160)
    removed_server_ids: list[int] = Field(default_factory=list, max_length=12)
    included_server_ids: list[int] | None = Field(default=None, max_length=12)
    server_overrides: list[SimulationServerOverride] = Field(default_factory=list, max_length=12)
    virtual_servers: list[VirtualServerInput] = Field(default_factory=list, max_length=12)
    load_units: list[SimulationLoadUnit] | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_server_sets(self) -> "SimulationRequest":
        if len(set(self.removed_server_ids)) != len(self.removed_server_ids):
            raise ValueError("removed_server_ids no puede contener duplicados")
        if self.included_server_ids is not None and len(set(self.included_server_ids)) != len(
            self.included_server_ids
        ):
            raise ValueError("included_server_ids no puede contener duplicados")
        if len({item.server_id for item in self.server_overrides}) != len(self.server_overrides):
            raise ValueError("server_overrides no puede contener duplicados")
        if len({item.key for item in self.virtual_servers}) != len(self.virtual_servers):
            raise ValueError("virtual_servers no puede contener duplicados")
        if self.included_server_ids is not None and set(self.removed_server_ids).intersection(
            self.included_server_ids
        ):
            raise ValueError("un servidor no puede estar incluido y eliminado")
        return self


class DistributionServerRead(BaseModel):
    """Resultado por servidor de una distribución."""

    key: str
    server_id: int | None
    name: str
    capacity_mbps: float
    operational_limit_mbps: float
    recommended_limit_mbps: float
    minimum_reserve_mbps: float
    assigned_load_mbps: float
    free_margin_mbps: float
    utilization_percent: float
    assigned_unit_count: int
    exceeds_operational_target: bool
    exceeds_recommended_limit: bool


class DistributionAssignmentRead(BaseModel):
    unit_id: str
    server_key: str | None
    load_mbps: float
    assigned: bool
    reason: str | None


class SimulationResult(BaseModel):
    """Resultado reproducible de una simulación."""

    feasible: bool
    data_quality: SimulationDataQuality
    risk: SimulationRisk
    explanation: str
    missing_data: list[str]
    servers: list[DistributionServerRead]
    assignments: list[DistributionAssignmentRead]
    unassigned_load_mbps: float
    unassigned_unit_count: int
    total_capacity_mbps: float
    total_assignable_capacity_mbps: float
    total_assigned_load_mbps: float
    current_monthly_cost: float | None
    proposed_monthly_cost: float | None
    monthly_savings: float | None
    annual_savings: float | None


class SimulationRead(BaseModel):
    """Simulación persistida como historial local."""

    id: int
    name: str
    request: SimulationRequest
    result: SimulationResult
    created_at: datetime
    updated_at: datetime


class SimulationListRead(BaseModel):
    items: list[SimulationRead]
    total: int
