"""Modelos ORM del dominio.

Importarlos aquí garantiza que ``Base.metadata`` conozca todas las
tablas (necesario para Alembic y para ``create_all`` en tests).
"""

from app.models.channel import Channel, ChannelMetric, ChannelStatus
from app.models.collection_run import CollectionRun, CollectionRunStatus, CollectionTrigger
from app.models.server import Server, ServerMetric, ServerRole

__all__ = [
    "Channel",
    "ChannelMetric",
    "ChannelStatus",
    "CollectionRun",
    "CollectionRunStatus",
    "CollectionTrigger",
    "Server",
    "ServerMetric",
    "ServerRole",
]
