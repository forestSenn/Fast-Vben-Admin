"""add file assets

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("avatar_url", sa.String(length=500), nullable=True))

    op.create_table(
        "fileasset",
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("extension", sa.String(length=20), nullable=True),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_provider", sa.String(length=50), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("public_url", sa.String(length=500), nullable=True),
        sa.Column("uploader_id", sa.UUID(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fileasset_sha256"), "fileasset", ["sha256"])
    op.create_index("ix_fileasset_created_at", "fileasset", ["created_at"])
    op.create_index("ix_fileasset_uploader_id", "fileasset", ["uploader_id"])


def downgrade() -> None:
    op.drop_index("ix_fileasset_uploader_id", table_name="fileasset")
    op.drop_index("ix_fileasset_created_at", table_name="fileasset")
    op.drop_index(op.f("ix_fileasset_sha256"), table_name="fileasset")
    op.drop_table("fileasset")
    op.drop_column("user", "avatar_url")
