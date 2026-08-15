"""Contratos de recomendaciones del motor de inteligencia determinista."""

import enum
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.simulations import SimulationDataQuality


class IntelligenceSeverity(enum.StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class IntelligenceRecommendation(BaseModel):
    """Recomendación explicable sin ejecutar acciones."""

    code: str
    severity: IntelligenceSeverity
    title: str
    explanation: str
    data_used: list[str]
    monthly_savings: float | None
    annual_savings: float | None
    risk: str
    confidence: float = Field(ge=0, le=1)
    suggested_action: str
    server_id: int | None = None
    server_name: str | None = None


class IntelligenceRecommendationsRead(BaseModel):
    generated_at: datetime
    data_quality: SimulationDataQuality
    recommendations: list[IntelligenceRecommendation]
