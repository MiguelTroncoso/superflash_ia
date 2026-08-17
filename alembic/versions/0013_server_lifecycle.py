"""Add safe lifecycle state for server inventory retirement.

The migration is additive. Existing inventory remains active and no metric,
alert, onboarding, or channel row is removed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "servers",
        sa.Column("lifecycle_state", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.add_column("servers", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_servers_lifecycle_state", "servers", ["lifecycle_state"])


def downgrade() -> None:
    op.drop_index("ix_servers_lifecycle_state", table_name="servers")
    op.drop_column("servers", "archived_at")
    op.drop_column("servers", "lifecycle_state")
