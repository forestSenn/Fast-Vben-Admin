"""add user mobile

Revision ID: 2d3e4f5a6b7c
Revises: 1cb1a9218afe
Create Date: 2026-07-15 14:30:00

"""

import sqlalchemy as sa
from alembic import op

revision = "2d3e4f5a6b7c"
down_revision = "1cb1a9218afe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("mobile", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_user_mobile"), "user", ["mobile"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_mobile"), table_name="user")
    op.drop_column("user", "mobile")
