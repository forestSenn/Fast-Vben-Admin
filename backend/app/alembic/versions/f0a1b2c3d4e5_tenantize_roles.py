"""tenantize roles

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-07-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f0a1b2c3d4e5"
down_revision: str | None = "e9f0a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_TENANT_ID = "00000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    op.add_column("role", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.execute(
        sa.text("UPDATE role SET tenant_id = CAST(:tenant_id AS UUID)").bindparams(
            tenant_id=DEFAULT_TENANT_ID
        )
    )
    op.alter_column("role", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_role_tenant_id_tenant",
        "role",
        "tenant",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index(op.f("ix_role_code"), table_name="role")
    op.create_index(op.f("ix_role_code"), "role", ["code"], unique=False)
    op.create_index(op.f("ix_role_tenant_id"), "role", ["tenant_id"], unique=False)
    op.create_unique_constraint(
        "uq_role_tenant_code", "role", ["tenant_id", "code"]
    )
    op.create_unique_constraint(
        "uq_role_id_tenant_id", "role", ["id", "tenant_id"]
    )

    op.add_column("userrole", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE userrole
            SET tenant_id = role.tenant_id
            FROM role
            WHERE role.id = userrole.role_id
            """
        )
    )
    op.alter_column("userrole", "tenant_id", nullable=False)
    op.drop_constraint("userrole_role_id_fkey", "userrole", type_="foreignkey")
    op.drop_constraint("userrole_user_id_fkey", "userrole", type_="foreignkey")
    op.drop_constraint("userrole_pkey", "userrole", type_="primary")
    op.create_primary_key(
        "userrole_pkey", "userrole", ["user_id", "role_id", "tenant_id"]
    )
    op.create_index(
        op.f("ix_userrole_tenant_id"), "userrole", ["tenant_id"], unique=False
    )
    op.create_foreign_key(
        "fk_userrole_membership",
        "userrole",
        "tenantmembership",
        ["user_id", "tenant_id"],
        ["user_id", "tenant_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_userrole_role_tenant",
        "userrole",
        "role",
        ["role_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_userrole_role_tenant", "userrole", type_="foreignkey")
    op.drop_constraint("fk_userrole_membership", "userrole", type_="foreignkey")
    op.drop_index(op.f("ix_userrole_tenant_id"), table_name="userrole")
    op.drop_constraint("userrole_pkey", "userrole", type_="primary")
    op.create_primary_key("userrole_pkey", "userrole", ["user_id", "role_id"])
    op.create_foreign_key(
        "userrole_user_id_fkey",
        "userrole",
        "user",
        ["user_id"],
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
    op.drop_column("userrole", "tenant_id")

    op.drop_constraint("uq_role_id_tenant_id", "role", type_="unique")
    op.drop_constraint("uq_role_tenant_code", "role", type_="unique")
    op.drop_index(op.f("ix_role_tenant_id"), table_name="role")
    op.drop_index(op.f("ix_role_code"), table_name="role")
    op.create_index(op.f("ix_role_code"), "role", ["code"], unique=True)
    op.drop_constraint("fk_role_tenant_id_tenant", "role", type_="foreignkey")
    op.drop_column("role", "tenant_id")
