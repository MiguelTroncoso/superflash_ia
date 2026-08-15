"""Contratos para capacidad de red y calidad de datos."""

import enum
from datetime import datetime

from pydantic import BaseModel


class CapacityState(enum.StrEnum):
    """Estado calculado de utilización de un servidor."""

    NORMAL = "normal"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"
    NO_DATA = "no_data"


class CapacityDataQuality(enum.StrEnum):
    """Origen y completitud de los datos usados en el cálculo."""

    OBSERVED = "observed"
    SIMULATED = "simulated"
    INSUFFICIENT_DATA = "insufficient_data"


class CapacityServerRead(BaseModel):
    """Capacidad calculada de un servidor habilitado."""

    server_id: int
    name: str
    provider: str | None
    group: str | None
    physical_capacity_mbps: float | None
    operational_limit_mbps: float | None
    recommended_limit_mbps: float | None
    minimum_reserve_mbps: float | None
    observed_load_mbps: float | None
    physical_utilization_percent: float | None
    operational_utilization_percent: float | None
    physical_free_mbps: float | None
    operational_free_mbps: float | None
    safety_margin_mbps: float | None
    state: CapacityState
    data_quality: CapacityDataQuality
    last_collected_at: datetime | None
    sample_count: int = 0
    average_load_mbps: float | None = None
    maximum_load_mbps: float | None = None
    p95_load_mbps: float | None = None
    p99_load_mbps: float | None = None
    headroom_mbps: float | None = None
    operational_margin_mbps: float | None = None
    free_capacity_mbps: float | None = None


class CapacityOverviewRead(BaseModel):
    """Resumen de capacidad de todos los servidores habilitados."""

    generated_at: datetime
    server_count: int
    configured_server_count: int
    sampled_server_count: int
    total_physical_capacity_mbps: float
    total_operational_limit_mbps: float
    total_observed_load_mbps: float
    total_physical_free_mbps: float
    total_operational_free_mbps: float
    data_quality: CapacityDataQuality
    missing_data: list[str]
    servers: list[CapacityServerRead]
