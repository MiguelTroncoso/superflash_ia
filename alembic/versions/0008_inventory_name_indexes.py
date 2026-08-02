"""Add indexes used by inventory ordering."""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_servers_name", "servers", ["name"])
    op.create_index("ix_channels_name", "channels", ["name"])


def downgrade() -> None:
    op.drop_index("ix_channels_name", table_name="channels")
    op.drop_index("ix_servers_name", table_name="servers")
