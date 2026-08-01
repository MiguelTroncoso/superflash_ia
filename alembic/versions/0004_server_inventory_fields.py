"""Extend servers with operational inventory fields.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("servers", sa.Column("provider", sa.String(length=120), nullable=True))
    op.add_column("servers", sa.Column("datacenter", sa.String(length=120), nullable=True))
    op.add_column("servers", sa.Column("group", sa.String(length=120), nullable=True))
    op.add_column(
        "servers",
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("servers", sa.Column("type", sa.String(length=80), nullable=True))
    op.add_column("servers", sa.Column("country", sa.String(length=2), nullable=True))
    op.add_column("servers", sa.Column("prometheus_url", sa.String(length=500), nullable=True))
    op.add_column("servers", sa.Column("prometheus_token", sa.String(length=1000), nullable=True))
    op.add_column(
        "servers",
        sa.Column("heartbeat_interval_seconds", sa.Integer(), nullable=False, server_default="300"),
    )
    op.add_column("servers", sa.Column("last_heartbeat_at", sa.DateTime(timezone=True)))
    op.add_column(
        "servers",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="unknown"),
    )
    op.add_column("servers", sa.Column("notes", sa.String(length=2000), nullable=True))
    op.create_index("ix_servers_provider", "servers", ["provider"])
    op.create_index("ix_servers_datacenter", "servers", ["datacenter"])
    op.create_index("ix_servers_group", "servers", ["group"])
    op.create_index("ix_servers_type", "servers", ["type"])
    op.create_index("ix_servers_country", "servers", ["country"])


def downgrade() -> None:
    op.drop_index("ix_servers_country", table_name="servers")
    op.drop_index("ix_servers_type", table_name="servers")
    op.drop_index("ix_servers_group", table_name="servers")
    op.drop_index("ix_servers_datacenter", table_name="servers")
    op.drop_index("ix_servers_provider", table_name="servers")
    for column in (
        "notes",
        "status",
        "last_heartbeat_at",
        "heartbeat_interval_seconds",
        "prometheus_token",
        "prometheus_url",
        "country",
        "type",
        "tags",
        "group",
        "datacenter",
        "provider",
    ):
        op.drop_column("servers", column)
