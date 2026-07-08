"""add audit logs

Revision ID: a1b2c3d4e5f6
Revises: 9e1f2a3b4c5d
Create Date: 2026-07-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9e1f2a3b4c5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "loginlog",
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("ip", sa.String(length=100), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_loginlog_created_at", "loginlog", ["created_at"])
    op.create_index("ix_loginlog_email", "loginlog", ["email"])

    op.create_table(
        "operationlog",
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("module", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(length=100), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("request_summary", sa.String(length=1000), nullable=True),
        sa.Column("response_summary", sa.String(length=1000), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operationlog_created_at", "operationlog", ["created_at"])
    op.create_index("ix_operationlog_path", "operationlog", ["path"])
    op.create_index("ix_operationlog_user_id", "operationlog", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_operationlog_user_id", table_name="operationlog")
    op.drop_index("ix_operationlog_path", table_name="operationlog")
    op.drop_index("ix_operationlog_created_at", table_name="operationlog")
    op.drop_table("operationlog")
    op.drop_index("ix_loginlog_email", table_name="loginlog")
    op.drop_index("ix_loginlog_created_at", table_name="loginlog")
    op.drop_table("loginlog")
