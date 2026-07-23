"""Heartbeat persistido para ejecuciones de recolección activas.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-23

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "collection_runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Filas existentes: el mejor heartbeat conocido es su propio inicio/fin.
    op.execute(
        "UPDATE collection_runs SET heartbeat_at = COALESCE(finished_at, started_at) "
        "WHERE heartbeat_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("collection_runs", "heartbeat_at")
