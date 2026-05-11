"""Add daily_stats table for taxi and other daily expenses

Revision ID: 003
Revises: 002
Create Date: 2026-05-11
"""
from alembic import op

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            order_date DATE PRIMARY KEY,
            taxi_cost  NUMERIC(10,2) NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS daily_stats")
