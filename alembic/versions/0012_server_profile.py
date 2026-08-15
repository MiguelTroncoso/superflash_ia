"""Add an explicit operational/financial profile to existing servers.

The column is additive, has a safe default for existing inventory, and does
not alter or remove any server or metric data.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "servers",
        sa.Column(
            "server_profile",
            sa.String(length=20),
            nullable=False,
            server_default="replaceable",
        ),
    )
    op.create_index("ix_servers_server_profile", "servers", ["server_profile"])


def downgrade() -> None:
    op.drop_index("ix_servers_server_profile", table_name="servers")
    op.drop_column("servers", "server_profile")
