"""Add optional manual network interface selection to managed servers."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("servers", sa.Column("network_interface", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("servers", "network_interface")
