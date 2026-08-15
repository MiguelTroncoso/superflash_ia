"""Add configurable capacity, server costs and simulation history.

The migration is additive. Existing servers keep their technical metrics and
receive nullable capacity-planning fields until an operator configures them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "servers",
        sa.Column("operational_network_limit_mbps", sa.Float(), nullable=True),
    )
    op.add_column(
        "servers",
        sa.Column("recommended_network_limit_mbps", sa.Float(), nullable=True),
    )
    op.add_column(
        "servers",
        sa.Column("minimum_network_reserve_mbps", sa.Float(), nullable=True),
    )
    op.add_column(
        "servers",
        sa.Column("candidate_for_replacement", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_servers_candidate_for_replacement", "servers", ["candidate_for_replacement"]
    )

    op.create_table(
        "server_cost_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("monthly_cost", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column(
            "billing_frequency", sa.String(length=20), nullable=False, server_default="monthly"
        ),
        sa.Column("next_payment_date", sa.Date(), nullable=True),
        sa.Column("provider", sa.String(length=120), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "payment_status", sa.String(length=20), nullable=False, server_default="pending"
        ),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("server_id", name="uq_server_cost_profiles_server_id"),
    )
    op.create_index(
        "ix_server_cost_profiles_next_payment", "server_cost_profiles", ["next_payment_date"]
    )
    op.create_index(
        "ix_server_cost_profiles_payment_status", "server_cost_profiles", ["payment_status"]
    )

    op.create_table(
        "simulations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_simulations_created_at", "simulations", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_simulations_created_at", table_name="simulations")
    op.drop_table("simulations")
    op.drop_index(
        "ix_server_cost_profiles_payment_status", table_name="server_cost_profiles"
    )
    op.drop_index("ix_server_cost_profiles_next_payment", table_name="server_cost_profiles")
    op.drop_table("server_cost_profiles")
    op.drop_index("ix_servers_candidate_for_replacement", table_name="servers")
    op.drop_column("servers", "candidate_for_replacement")
    op.drop_column("servers", "minimum_network_reserve_mbps")
    op.drop_column("servers", "recommended_network_limit_mbps")
    op.drop_column("servers", "operational_network_limit_mbps")
