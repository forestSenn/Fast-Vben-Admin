"""add tenant plans and quotas

Revision ID: f6a7b8c9d1e2
Revises: e5f6a7b8c0d1
Create Date: 2026-07-15 04:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d1e2"
down_revision: str | None = "e5f6a7b8c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_PLAN_ID = "00000000-0000-4000-8000-000000001001"


def upgrade() -> None:
    op.create_table(
        "tenantplan",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("max_members", sa.Integer(), nullable=True),
        sa.Column("max_file_assets", sa.Integer(), nullable=True),
        sa.Column("max_storage_bytes", sa.BigInteger(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tenantplan_code"),
        "tenantplan",
        ["code"],
        unique=True,
    )
    op.execute(
        sa.text(
            """
            INSERT INTO tenantplan (
                id,
                code,
                name,
                description,
                is_default,
                is_active,
                created_at,
                updated_at
            ) VALUES (
                CAST(:plan_id AS UUID),
                'standard',
                'Standard',
                'Default unlimited plan for migrated tenants.',
                TRUE,
                TRUE,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """
        ).bindparams(plan_id=DEFAULT_PLAN_ID)
    )

    op.add_column("tenant", sa.Column("plan_id", sa.UUID(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE tenant
            SET plan_id = CAST(:plan_id AS UUID)
            """
        ).bindparams(plan_id=DEFAULT_PLAN_ID)
    )
    op.alter_column("tenant", "plan_id", nullable=False)
    op.create_index(
        op.f("ix_tenant_plan_id"),
        "tenant",
        ["plan_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_tenant_plan_id_tenantplan",
        "tenant",
        "tenantplan",
        ["plan_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tenant_plan_id_tenantplan", "tenant", type_="foreignkey")
    op.drop_index(op.f("ix_tenant_plan_id"), table_name="tenant")
    op.drop_column("tenant", "plan_id")
    op.drop_index(op.f("ix_tenantplan_code"), table_name="tenantplan")
    op.drop_table("tenantplan")
