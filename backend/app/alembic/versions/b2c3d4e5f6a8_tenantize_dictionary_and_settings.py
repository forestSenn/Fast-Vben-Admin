"""tenantize dictionary and settings

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-07-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a8"
down_revision: str | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_TENANT_ID = "00000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    op.add_column("dictionarytype", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.add_column("dictionaryitem", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.add_column("systemsetting", sa.Column("tenant_id", sa.UUID(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE dictionarytype
            SET tenant_id = CAST(:tenant_id AS UUID)
            """
        ).bindparams(tenant_id=DEFAULT_TENANT_ID)
    )
    op.execute(
        sa.text(
            """
            UPDATE dictionaryitem
            SET tenant_id = dictionarytype.tenant_id
            FROM dictionarytype
            WHERE dictionarytype.id = dictionaryitem.type_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE systemsetting
            SET tenant_id = CAST(:tenant_id AS UUID)
            """
        ).bindparams(tenant_id=DEFAULT_TENANT_ID)
    )

    op.alter_column("dictionarytype", "tenant_id", nullable=False)
    op.alter_column("dictionaryitem", "tenant_id", nullable=False)
    op.alter_column("systemsetting", "tenant_id", nullable=False)

    op.drop_index(op.f("ix_dictionarytype_code"), table_name="dictionarytype")
    op.create_index(
        op.f("ix_dictionarytype_code"),
        "dictionarytype",
        ["code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dictionarytype_tenant_id"),
        "dictionarytype",
        ["tenant_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_dictionarytype_tenant_id_tenant",
        "dictionarytype",
        "tenant",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_dictionarytype_tenant_code",
        "dictionarytype",
        ["tenant_id", "code"],
    )
    op.create_unique_constraint(
        "uq_dictionarytype_id_tenant_id",
        "dictionarytype",
        ["id", "tenant_id"],
    )

    op.create_index(
        op.f("ix_dictionaryitem_tenant_id"),
        "dictionaryitem",
        ["tenant_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_dictionaryitem_tenant_id_tenant",
        "dictionaryitem",
        "tenant",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "dictionaryitem_type_id_fkey",
        "dictionaryitem",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_dictionaryitem_type_tenant",
        "dictionaryitem",
        "dictionarytype",
        ["type_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_dictionaryitem_tenant_type_value",
        "dictionaryitem",
        ["tenant_id", "type_id", "value"],
    )

    op.drop_index(op.f("ix_systemsetting_key"), table_name="systemsetting")
    op.create_index(
        op.f("ix_systemsetting_key"),
        "systemsetting",
        ["key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_systemsetting_tenant_id"),
        "systemsetting",
        ["tenant_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_systemsetting_tenant_id_tenant",
        "systemsetting",
        "tenant",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_systemsetting_tenant_key",
        "systemsetting",
        ["tenant_id", "key"],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM dictionaryitem
            WHERE tenant_id != CAST(:tenant_id AS UUID)
            """
        ).bindparams(tenant_id=DEFAULT_TENANT_ID)
    )
    op.execute(
        sa.text(
            """
            DELETE FROM dictionarytype
            WHERE tenant_id != CAST(:tenant_id AS UUID)
            """
        ).bindparams(tenant_id=DEFAULT_TENANT_ID)
    )
    op.execute(
        sa.text(
            """
            DELETE FROM systemsetting
            WHERE tenant_id != CAST(:tenant_id AS UUID)
            """
        ).bindparams(tenant_id=DEFAULT_TENANT_ID)
    )

    op.drop_constraint(
        "uq_systemsetting_tenant_key",
        "systemsetting",
        type_="unique",
    )
    op.drop_constraint(
        "fk_systemsetting_tenant_id_tenant",
        "systemsetting",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_systemsetting_tenant_id"), table_name="systemsetting")
    op.drop_index(op.f("ix_systemsetting_key"), table_name="systemsetting")
    op.create_index(
        op.f("ix_systemsetting_key"),
        "systemsetting",
        ["key"],
        unique=True,
    )

    op.drop_constraint(
        "uq_dictionaryitem_tenant_type_value",
        "dictionaryitem",
        type_="unique",
    )
    op.drop_constraint(
        "fk_dictionaryitem_type_tenant",
        "dictionaryitem",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "dictionaryitem_type_id_fkey",
        "dictionaryitem",
        "dictionarytype",
        ["type_id"],
        ["id"],
    )
    op.drop_constraint(
        "fk_dictionaryitem_tenant_id_tenant",
        "dictionaryitem",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_dictionaryitem_tenant_id"), table_name="dictionaryitem")

    op.drop_constraint(
        "uq_dictionarytype_id_tenant_id",
        "dictionarytype",
        type_="unique",
    )
    op.drop_constraint(
        "uq_dictionarytype_tenant_code",
        "dictionarytype",
        type_="unique",
    )
    op.drop_constraint(
        "fk_dictionarytype_tenant_id_tenant",
        "dictionarytype",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_dictionarytype_tenant_id"), table_name="dictionarytype")
    op.drop_index(op.f("ix_dictionarytype_code"), table_name="dictionarytype")
    op.create_index(
        op.f("ix_dictionarytype_code"),
        "dictionarytype",
        ["code"],
        unique=True,
    )

    op.drop_column("systemsetting", "tenant_id")
    op.drop_column("dictionaryitem", "tenant_id")
    op.drop_column("dictionarytype", "tenant_id")
