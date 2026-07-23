"""Esquema inicial: servidores, canales y métricas históricas.

Revision ID: 0001
Revises:
Create Date: 2026-07-23

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# BIGINT autoincremental en PostgreSQL; INTEGER en SQLite (tests locales).
BIG_INT_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "servers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("network_capacity_mbps", sa.Float(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_servers"),
    )
    op.create_index("ix_servers_external_id", "servers", ["external_id"], unique=True)

    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("current_server_id", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_channels"),
        sa.ForeignKeyConstraint(
            ["current_server_id"],
            ["servers.id"],
            name="fk_channels_current_server_id_servers",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_channels_external_id", "channels", ["external_id"], unique=True)
    op.create_index("ix_channels_category", "channels", ["category"])
    op.create_index("ix_channels_current_server_id", "channels", ["current_server_id"])

    op.create_table(
        "server_metrics",
        sa.Column("id", BIG_INT_PK, primary_key=True, autoincrement=True),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=False),
        sa.Column("memory_percent", sa.Float(), nullable=False),
        sa.Column("input_mbps", sa.Float(), nullable=False),
        sa.Column("output_mbps", sa.Float(), nullable=False),
        sa.Column("active_connections", sa.Integer(), nullable=False),
        sa.Column("active_streams", sa.Integer(), nullable=False),
        sa.Column("uptime_seconds", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_server_metrics"),
        sa.ForeignKeyConstraint(
            ["server_id"],
            ["servers.id"],
            name="fk_server_metrics_server_id_servers",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "server_id", "collected_at", name="uq_server_metrics_server_collected"
        ),
    )
    op.create_index("ix_server_metrics_server_id", "server_metrics", ["server_id"])
    op.create_index("ix_server_metrics_collected_at", "server_metrics", ["collected_at"])
    op.create_index(
        "ix_server_metrics_server_collected", "server_metrics", ["server_id", "collected_at"]
    )

    op.create_table(
        "channel_metrics",
        sa.Column("id", BIG_INT_PK, primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("viewers", sa.Integer(), nullable=False),
        sa.Column("bitrate_mbps", sa.Float(), nullable=True),
        sa.Column("estimated_output_mbps", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_channel_metrics"),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["channels.id"],
            name="fk_channel_metrics_channel_id_channels",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["server_id"],
            ["servers.id"],
            name="fk_channel_metrics_server_id_servers",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "channel_id", "collected_at", name="uq_channel_metrics_channel_collected"
        ),
    )
    op.create_index("ix_channel_metrics_channel_id", "channel_metrics", ["channel_id"])
    op.create_index("ix_channel_metrics_server_id", "channel_metrics", ["server_id"])
    op.create_index("ix_channel_metrics_collected_at", "channel_metrics", ["collected_at"])
    op.create_index(
        "ix_channel_metrics_channel_collected", "channel_metrics", ["channel_id", "collected_at"]
    )


def downgrade() -> None:
    op.drop_table("channel_metrics")
    op.drop_table("server_metrics")
    op.drop_table("channels")
    op.drop_table("servers")
