"""tenantize files and logs

Revision ID: c3d4e5f6a8b9
Revises: b2c3d4e5f6a8
Create Date: 2026-07-15 01:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a8b9"
down_revision: str | None = "b2c3d4e5f6a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_TENANT_ID = "00000000-0000-4000-8000-000000000001"
TENANT_TABLES = (
    "loginlog",
    "operationlog",
    "fileasset",
    "filestoragechannel",
)


def upgrade() -> None:
    for table_name in TENANT_TABLES:
        op.add_column(table_name, sa.Column("tenant_id", sa.UUID(), nullable=True))
        op.execute(
            sa.text(
                f"""
                UPDATE {table_name}
                SET tenant_id = CAST(:tenant_id AS UUID)
                """
            ).bindparams(tenant_id=DEFAULT_TENANT_ID)
        )
        op.alter_column(table_name, "tenant_id", nullable=False)
        op.create_index(
            op.f(f"ix_{table_name}_tenant_id"),
            table_name,
            ["tenant_id"],
            unique=False,
        )
        op.create_foreign_key(
            f"fk_{table_name}_tenant_id_tenant",
            table_name,
            "tenant",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.drop_index(
        op.f("ix_filestoragechannel_code"),
        table_name="filestoragechannel",
    )
    op.create_index(
        op.f("ix_filestoragechannel_code"),
        "filestoragechannel",
        ["code"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_filestoragechannel_tenant_code",
        "filestoragechannel",
        ["tenant_id", "code"],
    )


def downgrade() -> None:
    for table_name in TENANT_TABLES:
        op.execute(
            sa.text(
                f"""
                DELETE FROM {table_name}
                WHERE tenant_id != CAST(:tenant_id AS UUID)
                """
            ).bindparams(tenant_id=DEFAULT_TENANT_ID)
        )

    op.drop_constraint(
        "uq_filestoragechannel_tenant_code",
        "filestoragechannel",
        type_="unique",
    )
    op.drop_index(
        op.f("ix_filestoragechannel_code"),
        table_name="filestoragechannel",
    )
    op.create_index(
        op.f("ix_filestoragechannel_code"),
        "filestoragechannel",
        ["code"],
        unique=True,
    )

    for table_name in reversed(TENANT_TABLES):
        op.drop_constraint(
            f"fk_{table_name}_tenant_id_tenant",
            table_name,
            type_="foreignkey",
        )
        op.drop_index(
            op.f(f"ix_{table_name}_tenant_id"),
            table_name=table_name,
        )
        op.drop_column(table_name, "tenant_id")
