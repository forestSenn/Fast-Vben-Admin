"""Align the legacy tenant index name with the module schema.

Revision ID: items_rename_tenant_index
Revises: items_move_to_schema
Create Date: 2026-07-20

"""

from alembic import op

revision = "items_rename_tenant_index"
down_revision = "items_move_to_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER INDEX IF EXISTS items.ix_item_tenant_id "
        "RENAME TO ix_items_item_tenant_id"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX IF EXISTS items.ix_items_item_tenant_id "
        "RENAME TO ix_item_tenant_id"
    )
