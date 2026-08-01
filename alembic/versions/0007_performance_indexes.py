"""Add indexes for operational filtering and alert recency."""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_servers_status", "servers", ["status"])
    op.create_index(
        "ix_alerts_status_last_seen_at", "alerts", ["status", "last_seen_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_status_last_seen_at", table_name="alerts")
    op.drop_index("ix_servers_status", table_name="servers")
