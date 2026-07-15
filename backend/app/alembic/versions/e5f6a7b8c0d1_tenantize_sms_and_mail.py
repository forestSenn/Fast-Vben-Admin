"""tenantize sms and mail

Revision ID: e5f6a7b8c0d1
Revises: d4e5f6a7b9c0
Create Date: 2026-07-15 03:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c0d1"
down_revision: str | None = "d4e5f6a7b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_TENANT_ID = "00000000-0000-4000-8000-000000000001"
TENANT_TABLES = (
    "smschannel",
    "smstemplate",
    "smslog",
    "mailaccount",
    "mailtemplate",
    "maillog",
)


def add_tenant_column(table_name: str) -> None:
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


def tenantize_code(table_name: str) -> None:
    op.drop_index(op.f(f"ix_{table_name}_code"), table_name=table_name)
    op.create_index(
        op.f(f"ix_{table_name}_code"),
        table_name,
        ["code"],
        unique=False,
    )
    op.create_unique_constraint(
        f"uq_{table_name}_tenant_code",
        table_name,
        ["tenant_id", "code"],
    )
    op.create_unique_constraint(
        f"uq_{table_name}_id_tenant_id",
        table_name,
        ["id", "tenant_id"],
    )


def upgrade() -> None:
    for table_name in TENANT_TABLES:
        add_tenant_column(table_name)

    for table_name in (
        "smschannel",
        "smstemplate",
        "mailaccount",
        "mailtemplate",
    ):
        tenantize_code(table_name)

    op.drop_constraint("smstemplate_channel_id_fkey", "smstemplate", type_="foreignkey")
    op.drop_constraint("smslog_channel_id_fkey", "smslog", type_="foreignkey")
    op.drop_constraint("smslog_template_id_fkey", "smslog", type_="foreignkey")
    op.drop_constraint(
        "mailtemplate_account_id_fkey", "mailtemplate", type_="foreignkey"
    )
    op.drop_constraint("maillog_account_id_fkey", "maillog", type_="foreignkey")
    op.drop_constraint("maillog_template_id_fkey", "maillog", type_="foreignkey")

    op.create_foreign_key(
        "fk_smstemplate_channel_tenant",
        "smstemplate",
        "smschannel",
        ["channel_id", "tenant_id"],
        ["id", "tenant_id"],
    )
    op.create_foreign_key(
        "fk_smslog_channel_tenant",
        "smslog",
        "smschannel",
        ["channel_id", "tenant_id"],
        ["id", "tenant_id"],
    )
    op.create_foreign_key(
        "fk_smslog_template_tenant",
        "smslog",
        "smstemplate",
        ["template_id", "tenant_id"],
        ["id", "tenant_id"],
    )
    op.create_foreign_key(
        "fk_mailtemplate_account_tenant",
        "mailtemplate",
        "mailaccount",
        ["account_id", "tenant_id"],
        ["id", "tenant_id"],
    )
    op.create_foreign_key(
        "fk_maillog_account_tenant",
        "maillog",
        "mailaccount",
        ["account_id", "tenant_id"],
        ["id", "tenant_id"],
    )
    op.create_foreign_key(
        "fk_maillog_template_tenant",
        "maillog",
        "mailtemplate",
        ["template_id", "tenant_id"],
        ["id", "tenant_id"],
    )


def restore_global_code(table_name: str) -> None:
    op.drop_constraint(
        f"uq_{table_name}_id_tenant_id",
        table_name,
        type_="unique",
    )
    op.drop_constraint(
        f"uq_{table_name}_tenant_code",
        table_name,
        type_="unique",
    )
    op.drop_index(op.f(f"ix_{table_name}_code"), table_name=table_name)
    op.create_index(
        op.f(f"ix_{table_name}_code"),
        table_name,
        ["code"],
        unique=True,
    )


def downgrade() -> None:
    for table_name in (
        "smslog",
        "smstemplate",
        "smschannel",
        "maillog",
        "mailtemplate",
        "mailaccount",
    ):
        op.execute(
            sa.text(
                f"""
                DELETE FROM {table_name}
                WHERE tenant_id != CAST(:tenant_id AS UUID)
                """
            ).bindparams(tenant_id=DEFAULT_TENANT_ID)
        )

    op.drop_constraint("fk_maillog_template_tenant", "maillog", type_="foreignkey")
    op.drop_constraint("fk_maillog_account_tenant", "maillog", type_="foreignkey")
    op.drop_constraint(
        "fk_mailtemplate_account_tenant",
        "mailtemplate",
        type_="foreignkey",
    )
    op.drop_constraint("fk_smslog_template_tenant", "smslog", type_="foreignkey")
    op.drop_constraint("fk_smslog_channel_tenant", "smslog", type_="foreignkey")
    op.drop_constraint(
        "fk_smstemplate_channel_tenant",
        "smstemplate",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "smstemplate_channel_id_fkey",
        "smstemplate",
        "smschannel",
        ["channel_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "smslog_channel_id_fkey",
        "smslog",
        "smschannel",
        ["channel_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "smslog_template_id_fkey",
        "smslog",
        "smstemplate",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "mailtemplate_account_id_fkey",
        "mailtemplate",
        "mailaccount",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "maillog_account_id_fkey",
        "maillog",
        "mailaccount",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "maillog_template_id_fkey",
        "maillog",
        "mailtemplate",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )

    for table_name in (
        "mailtemplate",
        "mailaccount",
        "smstemplate",
        "smschannel",
    ):
        restore_global_code(table_name)

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
