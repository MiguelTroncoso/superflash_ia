"""Persist SSH host identity and managed exporter state.

All changes are additive and safe for existing inventory and metrics.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = (
        sa.Column("ssh_host_key_fingerprint", sa.String(length=100), nullable=True),
        sa.Column("ssh_management_configured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ssh_management_key_fingerprint", sa.String(length=100), nullable=True),
        sa.Column("ssh_management_key_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ssh_management_key_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("node_exporter_status", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("node_exporter_version", sa.String(length=40), nullable=True),
    )
    for column in columns:
        op.add_column("servers", column)


def downgrade() -> None:
    for name in (
        "node_exporter_version",
        "node_exporter_status",
        "ssh_management_key_rotated_at",
        "ssh_management_key_created_at",
        "ssh_management_key_fingerprint",
        "ssh_management_configured",
        "ssh_host_key_fingerprint",
    ):
        op.drop_column("servers", name)
