"""Modelos ORM del dominio.

Importarlos aquí garantiza que ``Base.metadata`` conozca todas las
tablas (necesario para Alembic y para ``create_all`` en tests).
"""

from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.channel import (
    Channel,
    ChannelCategoryHistory,
    ChannelEvent,
    ChannelMetric,
    ChannelStatus,
    ChannelType,
    TechnicalStream,
)
from app.models.collection_run import CollectionRun, CollectionRunStatus, CollectionTrigger
from app.models.onboarding import (
    OnboardingAuditEvent,
    ServerInventorySnapshot,
    ServerOnboarding,
)
from app.models.server import (
    Server,
    ServerLifecycleState,
    ServerMetric,
    ServerOperationalStatus,
    ServerRole,
)

__all__ = [
    "Alert",
    "AlertSeverity",
    "AlertStatus",
    "Channel",
    "ChannelCategoryHistory",
    "ChannelEvent",
    "ChannelMetric",
    "ChannelStatus",
    "ChannelType",
    "CollectionRun",
    "CollectionRunStatus",
    "CollectionTrigger",
    "OnboardingAuditEvent",
    "Server",
    "ServerInventorySnapshot",
    "ServerLifecycleState",
    "ServerMetric",
    "ServerOnboarding",
    "ServerOperationalStatus",
    "ServerRole",
    "TechnicalStream",
]
