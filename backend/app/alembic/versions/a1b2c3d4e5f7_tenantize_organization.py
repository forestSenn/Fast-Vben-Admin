"""tenantize organization

Revision ID: a1b2c3d4e5f7
Revises: f0a1b2c3d4e5
Create Date: 2026-07-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f7"
down_revision: str | None = "f0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_TENANT_ID = "00000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    op.add_column("department", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE department SET tenant_id = CAST(:tenant_id AS UUID)"
        ).bindparams(tenant_id=DEFAULT_TENANT_ID)
    )
    op.alter_column("department", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_department_tenant_id_tenant",
        "department",
        "tenant",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index(op.f("ix_department_code"), table_name="department")
    op.create_index(op.f("ix_department_code"), "department", ["code"], unique=False)
    op.create_index(
        op.f("ix_department_tenant_id"),
        "department",
        ["tenant_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_department_tenant_code", "department", ["tenant_id", "code"]
    )
    op.create_unique_constraint(
        "uq_department_id_tenant_id", "department", ["id", "tenant_id"]
    )
    op.drop_constraint("department_parent_id_fkey", "department", type_="foreignkey")
    op.drop_constraint(
        "department_leader_user_id_fkey", "department", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_department_parent_tenant",
        "department",
        "department",
        ["parent_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_department_leader_membership",
        "department",
        "tenantmembership",
        ["leader_user_id", "tenant_id"],
        ["user_id", "tenant_id"],
        ondelete="RESTRICT",
    )

    op.add_column("post", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.execute(
        sa.text("UPDATE post SET tenant_id = CAST(:tenant_id AS UUID)").bindparams(
            tenant_id=DEFAULT_TENANT_ID
        )
    )
    op.alter_column("post", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_post_tenant_id_tenant",
        "post",
        "tenant",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index(op.f("ix_post_code"), table_name="post")
    op.create_index(op.f("ix_post_code"), "post", ["code"], unique=False)
    op.create_index(op.f("ix_post_tenant_id"), "post", ["tenant_id"], unique=False)
    op.create_unique_constraint("uq_post_tenant_code", "post", ["tenant_id", "code"])
    op.create_unique_constraint("uq_post_id_tenant_id", "post", ["id", "tenant_id"])

    op.add_column(
        "tenantmembership", sa.Column("department_id", sa.UUID(), nullable=True)
    )
    op.create_index(
        op.f("ix_tenantmembership_department_id"),
        "tenantmembership",
        ["department_id"],
        unique=False,
    )
    op.execute(
        sa.text(
            """
            UPDATE tenantmembership
            SET department_id = "user".department_id
            FROM "user"
            WHERE tenantmembership.user_id = "user".id
              AND tenantmembership.tenant_id = CAST(:tenant_id AS UUID)
            """
        ).bindparams(tenant_id=DEFAULT_TENANT_ID)
    )
    op.create_foreign_key(
        "fk_tenantmembership_department_tenant",
        "tenantmembership",
        "department",
        ["department_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("fk_user_department_id_department", "user", type_="foreignkey")
    op.drop_column("user", "department_id")

    op.add_column("userpost", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE userpost
            SET tenant_id = post.tenant_id
            FROM post
            WHERE post.id = userpost.post_id
            """
        )
    )
    op.alter_column("userpost", "tenant_id", nullable=False)
    op.drop_constraint("userpost_user_id_fkey", "userpost", type_="foreignkey")
    op.drop_constraint("userpost_post_id_fkey", "userpost", type_="foreignkey")
    op.drop_constraint("userpost_pkey", "userpost", type_="primary")
    op.create_primary_key(
        "userpost_pkey", "userpost", ["user_id", "post_id", "tenant_id"]
    )
    op.create_index(
        op.f("ix_userpost_tenant_id"), "userpost", ["tenant_id"], unique=False
    )
    op.create_foreign_key(
        "fk_userpost_membership",
        "userpost",
        "tenantmembership",
        ["user_id", "tenant_id"],
        ["user_id", "tenant_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_userpost_post_tenant",
        "userpost",
        "post",
        ["post_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_userpost_post_tenant", "userpost", type_="foreignkey")
    op.drop_constraint("fk_userpost_membership", "userpost", type_="foreignkey")
    op.drop_index(op.f("ix_userpost_tenant_id"), table_name="userpost")
    op.drop_constraint("userpost_pkey", "userpost", type_="primary")
    op.create_primary_key("userpost_pkey", "userpost", ["user_id", "post_id"])
    op.create_foreign_key(
        "userpost_user_id_fkey",
        "userpost",
        "user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "userpost_post_id_fkey",
        "userpost",
        "post",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_column("userpost", "tenant_id")

    op.add_column("user", sa.Column("department_id", sa.UUID(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE "user"
            SET department_id = tenantmembership.department_id
            FROM tenantmembership
            WHERE tenantmembership.user_id = "user".id
              AND tenantmembership.tenant_id = CAST(:tenant_id AS UUID)
            """
        ).bindparams(tenant_id=DEFAULT_TENANT_ID)
    )
    op.create_foreign_key(
        "fk_user_department_id_department",
        "user",
        "department",
        ["department_id"],
        ["id"],
    )
    op.drop_constraint(
        "fk_tenantmembership_department_tenant",
        "tenantmembership",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_tenantmembership_department_id"), table_name="tenantmembership"
    )
    op.drop_column("tenantmembership", "department_id")

    op.drop_constraint("uq_post_id_tenant_id", "post", type_="unique")
    op.drop_constraint("uq_post_tenant_code", "post", type_="unique")
    op.drop_index(op.f("ix_post_tenant_id"), table_name="post")
    op.drop_index(op.f("ix_post_code"), table_name="post")
    op.create_index(op.f("ix_post_code"), "post", ["code"], unique=True)
    op.drop_constraint("fk_post_tenant_id_tenant", "post", type_="foreignkey")
    op.drop_column("post", "tenant_id")

    op.drop_constraint(
        "fk_department_leader_membership", "department", type_="foreignkey"
    )
    op.drop_constraint("fk_department_parent_tenant", "department", type_="foreignkey")
    op.create_foreign_key(
        "department_parent_id_fkey",
        "department",
        "department",
        ["parent_id"],
        ["id"],
    )
    op.create_foreign_key(
        "department_leader_user_id_fkey",
        "department",
        "user",
        ["leader_user_id"],
        ["id"],
    )
    op.drop_constraint("uq_department_id_tenant_id", "department", type_="unique")
    op.drop_constraint("uq_department_tenant_code", "department", type_="unique")
    op.drop_index(op.f("ix_department_tenant_id"), table_name="department")
    op.drop_index(op.f("ix_department_code"), table_name="department")
    op.create_index(op.f("ix_department_code"), "department", ["code"], unique=True)
    op.drop_constraint(
        "fk_department_tenant_id_tenant", "department", type_="foreignkey"
    )
    op.drop_column("department", "tenant_id")
