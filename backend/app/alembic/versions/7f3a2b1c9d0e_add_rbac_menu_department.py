"""add rbac menu department

Revision ID: 7f3a2b1c9d0e
Revises: 2c8d9a6f1b21
Create Date: 2026-07-07 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7f3a2b1c9d0e"
down_revision: Union[str, None] = "2c8d9a6f1b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "department",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("leader_user_id", sa.UUID(), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["leader_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["department.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_department_code"), "department", ["code"], unique=True)

    op.create_table(
        "menu",
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("route_path", sa.String(length=255), nullable=True),
        sa.Column("route_name", sa.String(length=100), nullable=True),
        sa.Column("component", sa.String(length=255), nullable=True),
        sa.Column("icon", sa.String(length=100), nullable=True),
        sa.Column("permission_code", sa.String(length=100), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False),
        sa.Column("is_keep_alive", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["menu.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_menu_permission_code"), "menu", ["permission_code"], unique=False
    )

    op.create_table(
        "role",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_role_code"), "role", ["code"], unique=True)

    op.add_column("user", sa.Column("department_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_user_department_id_department",
        "user",
        "department",
        ["department_id"],
        ["id"],
    )

    op.create_table(
        "rolemenu",
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("menu_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["menu_id"], ["menu.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "menu_id"),
    )
    op.create_table(
        "userrole",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )


def downgrade() -> None:
    op.drop_table("userrole")
    op.drop_table("rolemenu")
    op.drop_constraint("fk_user_department_id_department", "user", type_="foreignkey")
    op.drop_column("user", "department_id")
    op.drop_index(op.f("ix_role_code"), table_name="role")
    op.drop_table("role")
    op.drop_index(op.f("ix_menu_permission_code"), table_name="menu")
    op.drop_table("menu")
    op.drop_index(op.f("ix_department_code"), table_name="department")
    op.drop_table("department")
