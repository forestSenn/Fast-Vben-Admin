"""Items module baseline.

Revision ID: items_baseline
Revises: None
Create Date: 2026-07-20

"""

import sqlalchemy as sa
from alembic import op

revision = "items_baseline"
down_revision = None
branch_labels = ("items",)
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    op.execute("CREATE SCHEMA IF NOT EXISTS items")
    # Existing installations still have the legacy table in public until the
    # following revision transfers it. New editions create only the module table.
    if not inspector.has_table("item", schema="public") and not inspector.has_table(
        "item", schema="items"
    ):
        op.create_table(
            "item",
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("owner_id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            schema="items",
        )
        op.create_index(
            "ix_items_item_tenant_id", "item", ["tenant_id"], schema="items"
        )


def downgrade() -> None:
    raise NotImplementedError("Items baseline is not downgraded in production")
