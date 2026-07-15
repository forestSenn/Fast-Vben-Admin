"""add role data permissions

Revision ID: a7b8c9d1e2f3
Revises: f6a7b8c9d1e2
Create Date: 2026-07-15 06:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d1e2f3"
down_revision: str | None = "f6a7b8c9d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "role",
        sa.Column(
            "data_scope",
            sa.String(length=32),
            nullable=False,
            server_default="self",
        ),
    )
    op.create_check_constraint(
        "ck_role_data_scope",
        "role",
        "data_scope IN ('all', 'department', 'department_and_children', 'self', 'custom')",
    )
    op.execute(
        sa.text(
            "UPDATE role SET data_scope = 'all' WHERE code IN ('super_admin', 'admin')"
        )
    )
    op.alter_column("role", "data_scope", server_default=None)

    op.create_table(
        "roledatascopedepartment",
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["role_id", "tenant_id"],
            ["role.id", "role.tenant_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["department_id", "tenant_id"],
            ["department.id", "department.tenant_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "department_id", "tenant_id"),
    )
    op.create_index(
        op.f("ix_roledatascopedepartment_tenant_id"),
        "roledatascopedepartment",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_roledatascopedepartment_tenant_id"),
        table_name="roledatascopedepartment",
    )
    op.drop_table("roledatascopedepartment")
    op.drop_constraint("ck_role_data_scope", "role", type_="check")
    op.drop_column("role", "data_scope")
