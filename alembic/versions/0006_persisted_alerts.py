"""Persist alert lifecycle and severity.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("fingerprint", sa.String(length=220), nullable=False),
        sa.Column("type", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("server_name", sa.String(length=200), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("fingerprint", name="uq_alerts_fingerprint"),
    )
    op.create_index("ix_alerts_fingerprint", "alerts", ["fingerprint"])
    op.create_index("ix_alerts_type", "alerts", ["type"])
    op.create_index("ix_alerts_server_id", "alerts", ["server_id"])
    op.create_index("ix_alerts_server_status", "alerts", ["server_id", "status"])


def downgrade() -> None:
    op.drop_table("alerts")
