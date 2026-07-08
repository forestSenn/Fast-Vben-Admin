"""add cascade to rbac links

Revision ID: 8d4e5f6a7b8c
Revises: 7f3a2b1c9d0e
Create Date: 2026-07-07 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8d4e5f6a7b8c"
down_revision: Union[str, None] = "7f3a2b1c9d0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("rolemenu_menu_id_fkey", "rolemenu", type_="foreignkey")
    op.drop_constraint("rolemenu_role_id_fkey", "rolemenu", type_="foreignkey")
    op.drop_constraint("userrole_role_id_fkey", "userrole", type_="foreignkey")
    op.drop_constraint("userrole_user_id_fkey", "userrole", type_="foreignkey")
    op.create_foreign_key(
        "rolemenu_menu_id_fkey",
        "rolemenu",
        "menu",
        ["menu_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "rolemenu_role_id_fkey",
        "rolemenu",
        "role",
        ["role_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "userrole_role_id_fkey",
        "userrole",
        "role",
        ["role_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "userrole_user_id_fkey",
        "userrole",
        "user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("userrole_user_id_fkey", "userrole", type_="foreignkey")
    op.drop_constraint("userrole_role_id_fkey", "userrole", type_="foreignkey")
    op.drop_constraint("rolemenu_role_id_fkey", "rolemenu", type_="foreignkey")
    op.drop_constraint("rolemenu_menu_id_fkey", "rolemenu", type_="foreignkey")
    op.create_foreign_key(
        "userrole_user_id_fkey", "userrole", "user", ["user_id"], ["id"]
    )
    op.create_foreign_key(
        "userrole_role_id_fkey", "userrole", "role", ["role_id"], ["id"]
    )
    op.create_foreign_key(
        "rolemenu_role_id_fkey", "rolemenu", "role", ["role_id"], ["id"]
    )
    op.create_foreign_key(
        "rolemenu_menu_id_fkey", "rolemenu", "menu", ["menu_id"], ["id"]
    )
