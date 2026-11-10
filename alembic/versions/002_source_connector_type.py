"""Persist connector implementation key separately from source category.

Revision ID: 002_source_connector_type
Revises: 001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "002_source_connector_type"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("connector_type", sa.String(length=50), nullable=True))
    op.create_index("ix_sources_connector_type", "sources", ["connector_type"])
    # Safe best-effort backfill for rows whose source key already names the connector.
    op.execute(
        "UPDATE sources SET connector_type = name "
        "WHERE name IN ('telegram_mtproto', 'telegram_bot') AND connector_type IS NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_sources_connector_type", table_name="sources")
    op.drop_column("sources", "connector_type")
