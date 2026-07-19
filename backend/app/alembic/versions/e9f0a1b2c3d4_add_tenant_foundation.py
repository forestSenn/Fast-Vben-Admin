"""add tenant foundation

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-07-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9f0a1b2c3d4"
down_revision: str | None = "d8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_TENANT_ID = "00000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    op.create_table(
        "tenant",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenant_code"), "tenant", ["code"], unique=True)
    op.execute(
        sa.text(
            """
            INSERT INTO tenant (id, code, name, description, is_active, created_at, updated_at)
            VALUES (
                CAST(:tenant_id AS UUID),
                'default',
                'Default Tenant',
                'Tenant created for data that predates v2.0 multi-tenancy.',
                TRUE,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """
        ).bindparams(tenant_id=DEFAULT_TENANT_ID)
    )

    op.create_table(
        "tenantmembership",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "tenant_id"),
    )
    op.create_index(
        op.f("ix_tenantmembership_tenant_id"),
        "tenantmembership",
        ["tenant_id"],
        unique=False,
    )
    op.execute(
        sa.text(
            """
            INSERT INTO tenantmembership
                (user_id, tenant_id, is_active, is_default, created_at)
            SELECT id, CAST(:tenant_id AS UUID), TRUE, TRUE, CURRENT_TIMESTAMP
            FROM "user"
            """
        ).bindparams(tenant_id=DEFAULT_TENANT_ID)
    )

    op.add_column("usersession", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.execute(
        sa.text("UPDATE usersession SET tenant_id = CAST(:tenant_id AS UUID)").bindparams(
            tenant_id=DEFAULT_TENANT_ID
        )
    )
    op.alter_column("usersession", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_usersession_tenant_id_tenant",
        "usersession",
        "tenant",
        ["tenant_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_usersession_tenant_id"),
        "usersession",
        ["tenant_id"],
        unique=False,
    )

    if sa.inspect(op.get_bind()).has_table("item"):
        op.add_column("item", sa.Column("tenant_id", sa.UUID(), nullable=True))
        op.execute(
            sa.text("UPDATE item SET tenant_id = CAST(:tenant_id AS UUID)").bindparams(
                tenant_id=DEFAULT_TENANT_ID
            )
        )
        op.alter_column("item", "tenant_id", nullable=False)
        op.create_foreign_key(
            "fk_item_tenant_id_tenant",
            "item",
            "tenant",
            ["tenant_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_index(op.f("ix_item_tenant_id"), "item", ["tenant_id"], unique=False)


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("item"):
        op.drop_index(op.f("ix_item_tenant_id"), table_name="item")
        op.drop_constraint("fk_item_tenant_id_tenant", "item", type_="foreignkey")
        op.drop_column("item", "tenant_id")
    op.drop_index(op.f("ix_usersession_tenant_id"), table_name="usersession")
    op.drop_constraint(
        "fk_usersession_tenant_id_tenant", "usersession", type_="foreignkey"
    )
    op.drop_column("usersession", "tenant_id")
    op.drop_index(
        op.f("ix_tenantmembership_tenant_id"), table_name="tenantmembership"
    )
    op.drop_table("tenantmembership")
    op.drop_index(op.f("ix_tenant_code"), table_name="tenant")
    op.drop_table("tenant")
