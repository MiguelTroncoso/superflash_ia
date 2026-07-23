"""Historial de recolecciones y disk_percent en métricas de servidor.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-23

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BIG_INT_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.add_column("server_metrics", sa.Column("disk_percent", sa.Float(), nullable=True))

    op.create_table(
        "collection_runs",
        sa.Column("id", BIG_INT_PK, primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("triggered_by", sa.String(length=20), nullable=False),
        sa.Column("servers_synced", sa.Integer(), nullable=False),
        sa.Column("channels_synced", sa.Integer(), nullable=False),
        sa.Column("server_metrics_inserted", sa.Integer(), nullable=False),
        sa.Column("server_metrics_skipped", sa.Integer(), nullable=False),
        sa.Column("channel_metrics_inserted", sa.Integer(), nullable=False),
        sa.Column("channel_metrics_skipped", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_collection_runs"),
    )
    op.create_index("ix_collection_runs_started_at", "collection_runs", ["started_at"])


def downgrade() -> None:
    op.drop_table("collection_runs")
    op.drop_column("server_metrics", "disk_percent")
