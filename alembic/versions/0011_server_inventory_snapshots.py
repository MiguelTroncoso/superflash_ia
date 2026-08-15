"""Persist technical inventory discovered from real Prometheus targets.

The migration is additive. Existing servers and metric history remain
untouched; the new table is removed only by its own downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "server_inventory_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="prometheus"),
        sa.Column("node_exporter_version", sa.String(length=80), nullable=True),
        sa.Column("prometheus_last_scrape_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("probe_latency_ms", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("inventory", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "server_id", "captured_at", name="uq_server_inventory_server_captured"
        ),
    )
    op.create_index(
        "ix_server_inventory_server_id", "server_inventory_snapshots", ["server_id"]
    )
    op.create_index(
        "ix_server_inventory_captured_at", "server_inventory_snapshots", ["captured_at"]
    )
    op.create_index(
        "ix_server_inventory_status", "server_inventory_snapshots", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_server_inventory_status", table_name="server_inventory_snapshots")
    op.drop_index("ix_server_inventory_captured_at", table_name="server_inventory_snapshots")
    op.drop_index("ix_server_inventory_server_id", table_name="server_inventory_snapshots")
    op.drop_table("server_inventory_snapshots")
