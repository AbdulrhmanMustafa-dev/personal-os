"""Persist source enabled state independently of connection status.

Revision ID: 003_source_enabled
Revises: 002_source_connector_type
"""
from alembic import op
import sqlalchemy as sa

revision = "003_source_enabled"
down_revision = "002_source_connector_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_sources_enabled", "sources", ["enabled"])


def downgrade() -> None:
    op.drop_index("ix_sources_enabled", table_name="sources")
    op.drop_column("sources", "enabled")
