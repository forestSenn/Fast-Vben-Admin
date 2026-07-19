"""Move Items data into its module-owned schema.

Revision ID: items_move_to_schema
Revises: items_baseline
Create Date: 2026-07-20

"""

import sqlalchemy as sa
from alembic import op

revision = "items_move_to_schema"
down_revision = "items_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS items")
    if sa.inspect(op.get_bind()).has_table("item", schema="public"):
        op.execute("ALTER TABLE public.item SET SCHEMA items")


def downgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS items.item SET SCHEMA public")
