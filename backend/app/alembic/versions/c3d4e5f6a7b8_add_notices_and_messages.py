"""add notices and messages

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notice",
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.String(length=10000), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notice_created_at", "notice", ["created_at"])
    op.create_index("ix_notice_published_at", "notice", ["published_at"])
    op.create_index("ix_notice_status", "notice", ["status"])

    op.create_table(
        "usermessage",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("notice_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.String(length=10000), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["notice_id"], ["notice.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_usermessage_user_id"), "usermessage", ["user_id"])
    op.create_index("ix_usermessage_created_at", "usermessage", ["created_at"])
    op.create_index("ix_usermessage_notice_id", "usermessage", ["notice_id"])


def downgrade() -> None:
    op.drop_index("ix_usermessage_notice_id", table_name="usermessage")
    op.drop_index("ix_usermessage_created_at", table_name="usermessage")
    op.drop_index(op.f("ix_usermessage_user_id"), table_name="usermessage")
    op.drop_table("usermessage")
    op.drop_index("ix_notice_status", table_name="notice")
    op.drop_index("ix_notice_published_at", table_name="notice")
    op.drop_index("ix_notice_created_at", table_name="notice")
    op.drop_table("notice")
