"""Add missing columns and daily_number unique constraint

Revision ID: 002
Revises: 001
Create Date: 2026-05-08
"""
from alembic import op

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Columns added after initial deploy (safe with IF NOT EXISTS)
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS team VARCHAR(50)")
    op.execute("ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS label VARCHAR(255)")
    op.execute("ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS role VARCHAR(50) NOT NULL DEFAULT 'employee'")
    op.execute("ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS initial_debt NUMERIC(10,2) NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE cancel_requests ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ")
    op.execute("ALTER TABLE cancel_requests ADD COLUMN IF NOT EXISTS resolved_by BIGINT")

    # Unique constraint on daily_number per day (partial: only when not null)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_date_daily_number
        ON orders(order_date, daily_number)
        WHERE daily_number IS NOT NULL
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_orders_date_daily_number")
    op.execute("ALTER TABLE cancel_requests DROP COLUMN IF EXISTS resolved_by")
    op.execute("ALTER TABLE cancel_requests DROP COLUMN IF EXISTS resolved_at")
    op.execute("ALTER TABLE invite_codes DROP COLUMN IF EXISTS initial_debt")
    op.execute("ALTER TABLE invite_codes DROP COLUMN IF EXISTS role")
    op.execute("ALTER TABLE invite_codes DROP COLUMN IF EXISTS label")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS team")
