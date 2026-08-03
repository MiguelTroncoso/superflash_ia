"""Add source-aware channel lifecycle, events and technical streams.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-02

The migration is additive. Existing channels are assigned the ``legacy``
source and retain their metrics; the synchronizer can adopt those rows on
the first observation from their configured source instead of duplicating
them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category_id", sa.String(length=100), nullable=True),
        sa.Column("category_name", sa.String(length=100), nullable=True),
        sa.Column("event_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "source_id", "external_id", name="uq_channel_events_source_external"
        ),
    )
    op.create_index("ix_channel_events_source_id", "channel_events", ["source_id"])
    op.create_index("ix_channel_events_category_id", "channel_events", ["category_id"])
    op.create_index("ix_channel_events_event_start_at", "channel_events", ["event_start_at"])
    op.create_index("ix_channel_events_last_seen_at", "channel_events", ["last_seen_at"])
    op.create_index("ix_channel_events_active", "channel_events", ["active"])
    op.create_index(
        "ix_channel_events_source_start", "channel_events", ["source_id", "event_start_at"]
    )

    op.create_table(
        "technical_streams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint(
            "source_id", "external_id", name="uq_technical_streams_source_external"
        ),
    )
    op.create_index("ix_technical_streams_source_id", "technical_streams", ["source_id"])
    op.create_index("ix_technical_streams_last_seen_at", "technical_streams", ["last_seen_at"])
    op.create_index("ix_technical_streams_active", "technical_streams", ["active"])

    channel_columns = (
        sa.Column("source_id", sa.String(length=120), nullable=False, server_default="legacy"),
        sa.Column("category_id", sa.String(length=100), nullable=True),
        sa.Column(
            "channel_type",
            sa.String(length=20),
            nullable=False,
            server_default="permanent",
        ),
        sa.Column("event_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("inactive_since_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("technical_stream_id", sa.Integer(), nullable=True),
    )
    for column in channel_columns:
        op.add_column("channels", column)

    op.add_column("channel_metrics", sa.Column("event_id", sa.Integer(), nullable=True))
    op.add_column(
        "channel_metrics", sa.Column("technical_stream_id", sa.Integer(), nullable=True)
    )
    for name in (
        "channels_created",
        "channels_updated",
        "channels_reactivated",
        "channels_deactivated",
        "channels_archived",
        "channels_unchanged",
        "channels_failed",
    ):
        op.add_column(
            "collection_runs",
            sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
        )

    op.create_foreign_key(
        "fk_channels_event_id_channel_events",
        "channels",
        "channel_events",
        ["event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_channels_technical_stream_id_technical_streams",
        "channels",
        "technical_streams",
        ["technical_stream_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_channel_metrics_event_id_channel_events",
        "channel_metrics",
        "channel_events",
        ["event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_channel_metrics_technical_stream_id_technical_streams",
        "channel_metrics",
        "technical_streams",
        ["technical_stream_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "channel_category_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("category_id", sa.String(length=100), nullable=True),
        sa.Column("category_name", sa.String(length=100), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["channel_id"], ["channels.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_channel_category_history_channel_id", "channel_category_history", ["channel_id"]
    )
    op.create_index(
        "ix_channel_category_history_channel_valid_from",
        "channel_category_history",
        ["channel_id", "valid_from"],
    )

    # Preserve the current category as the first historical interval.
    op.execute(
        sa.text(
            """
            INSERT INTO channel_category_history
                (channel_id, source_id, category_id, category_name, valid_from, valid_to)
            SELECT id, source_id, category_id, category, created_at, NULL
            FROM channels
            """
        )
    )

    # The old schema had a global external_id uniqueness rule. Replace it
    # with source-aware identity while retaining a normal search index.
    op.drop_index("ix_channels_external_id", table_name="channels")
    op.create_index("ix_channels_external_id", "channels", ["external_id"])
    op.create_unique_constraint(
        "uq_channels_source_external", "channels", ["source_id", "external_id"]
    )
    op.create_index("ix_channels_category_id", "channels", ["category_id"])
    op.create_index("ix_channels_source_active", "channels", ["source_id", "active"])
    op.create_index("ix_channels_type_active", "channels", ["channel_type", "active"])
    op.create_index("ix_channels_event_start_at", "channels", ["event_start_at"])
    op.create_index("ix_channels_last_seen_at", "channels", ["last_seen_at"])
    op.create_index("ix_channels_event_id", "channels", ["event_id"])
    op.create_index("ix_channels_technical_stream_id", "channels", ["technical_stream_id"])
    op.create_index("ix_channel_metrics_event_id", "channel_metrics", ["event_id"])
    op.create_index(
        "ix_channel_metrics_technical_stream_id", "channel_metrics", ["technical_stream_id"]
    )


def downgrade() -> None:
    for name in (
        "channels_failed",
        "channels_unchanged",
        "channels_archived",
        "channels_deactivated",
        "channels_reactivated",
        "channels_updated",
        "channels_created",
    ):
        op.drop_column("collection_runs", name)

    op.drop_index(
        "ix_channel_metrics_technical_stream_id", table_name="channel_metrics"
    )
    op.drop_index("ix_channel_metrics_event_id", table_name="channel_metrics")
    op.drop_index("ix_channels_technical_stream_id", table_name="channels")
    op.drop_index("ix_channels_event_id", table_name="channels")
    op.drop_index("ix_channels_last_seen_at", table_name="channels")
    op.drop_index("ix_channels_event_start_at", table_name="channels")
    op.drop_index("ix_channels_type_active", table_name="channels")
    op.drop_index("ix_channels_source_active", table_name="channels")
    op.drop_index("ix_channels_category_id", table_name="channels")
    op.drop_constraint("uq_channels_source_external", "channels", type_="unique")
    op.drop_index("ix_channels_external_id", table_name="channels")
    op.create_index("ix_channels_external_id", "channels", ["external_id"], unique=True)

    op.drop_constraint(
        "fk_channel_metrics_technical_stream_id_technical_streams",
        "channel_metrics",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_channel_metrics_event_id_channel_events",
        "channel_metrics",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_channels_technical_stream_id_technical_streams",
        "channels",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_channels_event_id_channel_events", "channels", type_="foreignkey"
    )

    op.drop_index(
        "ix_channel_category_history_channel_valid_from", table_name="channel_category_history"
    )
    op.drop_index(
        "ix_channel_category_history_channel_id", table_name="channel_category_history"
    )
    op.drop_table("channel_category_history")

    op.drop_column("channel_metrics", "technical_stream_id")
    op.drop_column("channel_metrics", "event_id")

    for column in (
        "technical_stream_id",
        "event_id",
        "source_updated_at",
        "archived_at",
        "inactive_since_at",
        "active",
        "last_seen_at",
        "first_seen_at",
        "event_end_at",
        "event_start_at",
        "channel_type",
        "category_id",
        "source_id",
    ):
        op.drop_column("channels", column)

    op.drop_index("ix_technical_streams_active", table_name="technical_streams")
    op.drop_index("ix_technical_streams_last_seen_at", table_name="technical_streams")
    op.drop_index("ix_technical_streams_source_id", table_name="technical_streams")
    op.drop_table("technical_streams")

    op.drop_index("ix_channel_events_source_start", table_name="channel_events")
    op.drop_index("ix_channel_events_active", table_name="channel_events")
    op.drop_index("ix_channel_events_last_seen_at", table_name="channel_events")
    op.drop_index("ix_channel_events_event_start_at", table_name="channel_events")
    op.drop_index("ix_channel_events_category_id", table_name="channel_events")
    op.drop_index("ix_channel_events_source_id", table_name="channel_events")
    op.drop_table("channel_events")
