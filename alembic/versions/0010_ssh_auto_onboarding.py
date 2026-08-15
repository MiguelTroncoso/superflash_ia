"""Add SSH onboarding state, audit and technical inventory history.

All additions are nullable or have safe defaults. No existing server,
channel or metric row is deleted or rewritten.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    server_columns = (
        sa.Column("network_interface", sa.String(length=100), nullable=True),
        sa.Column("operational_network_limit_mbps", sa.Float(), nullable=True),
        sa.Column("recommended_network_limit_mbps", sa.Float(), nullable=True),
        sa.Column("minimum_network_reserve_mbps", sa.Float(), nullable=True),
        sa.Column("monthly_cost", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("next_payment_date", sa.Date(), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("contract_status", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("ssh_port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("ssh_username", sa.String(length=120), nullable=True),
        sa.Column("prometheus_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    for column in server_columns:
        op.add_column("servers", column)
    op.create_index("ix_servers_network_interface", "servers", ["network_interface"])

    op.create_table(
        "server_inventory_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="ssh_onboarding"),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("inventory", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "server_id", "fingerprint", name="uq_server_inventory_server_fingerprint"
        ),
    )
    op.create_index(
        "ix_server_inventory_server_captured",
        "server_inventory_snapshots",
        ["server_id", "captured_at"],
    )

    op.create_table(
        "server_onboardings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("current_step", sa.String(length=60), nullable=False, server_default="pending"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("last_error_message_sanitized", sa.String(length=500), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_successful_step", sa.String(length=60), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("auth_method", sa.String(length=20), nullable=False),
        sa.Column("ssh_port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("ssh_username", sa.String(length=120), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_server_onboardings_server_created",
        "server_onboardings",
        ["server_id", "created_at"],
    )
    op.create_index("ix_server_onboardings_status", "server_onboardings", ["status"])

    op.create_table(
        "onboarding_audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("onboarding_id", sa.BigInteger(), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("event", sa.String(length=80), nullable=False),
        sa.Column("step", sa.String(length=60), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("detail_sanitized", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["onboarding_id"], ["server_onboardings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_onboarding_audit_onboarding_created",
        "onboarding_audit_events",
        ["onboarding_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_onboarding_audit_onboarding_created", table_name="onboarding_audit_events")
    op.drop_table("onboarding_audit_events")
    op.drop_index("ix_server_onboardings_status", table_name="server_onboardings")
    op.drop_index("ix_server_onboardings_server_created", table_name="server_onboardings")
    op.drop_table("server_onboardings")
    op.drop_index("ix_server_inventory_server_captured", table_name="server_inventory_snapshots")
    op.drop_table("server_inventory_snapshots")
    op.drop_index("ix_servers_network_interface", table_name="servers")
    for name in (
        "prometheus_active",
        "ssh_username",
        "ssh_port",
        "contract_status",
        "auto_renew",
        "next_payment_date",
        "currency",
        "monthly_cost",
        "minimum_network_reserve_mbps",
        "recommended_network_limit_mbps",
        "operational_network_limit_mbps",
        "network_interface",
    ):
        op.drop_column("servers", name)
