"""Persist extended infrastructure metrics.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in (
        "filesystem_percent",
        "swap_percent",
        "io_read_mbps",
        "io_write_mbps",
        "load_average_1m",
        "load_average_5m",
        "load_average_15m",
    ):
        op.add_column("server_metrics", sa.Column(name, sa.Float(), nullable=True))


def downgrade() -> None:
    for name in (
        "load_average_15m",
        "load_average_5m",
        "load_average_1m",
        "io_write_mbps",
        "io_read_mbps",
        "swap_percent",
        "filesystem_percent",
    ):
        op.drop_column("server_metrics", name)
