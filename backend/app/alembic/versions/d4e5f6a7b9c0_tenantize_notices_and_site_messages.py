"""tenantize notices and site messages

Revision ID: d4e5f6a7b9c0
Revises: c3d4e5f6a8b9
Create Date: 2026-07-15 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b9c0"
down_revision: str | None = "c3d4e5f6a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_TENANT_ID = "00000000-0000-4000-8000-000000000001"


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


def upgrade() -> None:
    add_tenant_column("notice")
    add_tenant_column("sitemessagetemplate")
    add_tenant_column("usermessage")

    op.create_unique_constraint(
        "uq_notice_id_tenant_id",
        "notice",
        ["id", "tenant_id"],
    )

    op.drop_index(
        op.f("ix_sitemessagetemplate_code"),
        table_name="sitemessagetemplate",
    )
    op.create_index(
        op.f("ix_sitemessagetemplate_code"),
        "sitemessagetemplate",
        ["code"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_sitemessagetemplate_tenant_code",
        "sitemessagetemplate",
        ["tenant_id", "code"],
    )
    op.create_unique_constraint(
        "uq_sitemessagetemplate_id_tenant_id",
        "sitemessagetemplate",
        ["id", "tenant_id"],
    )

    op.drop_constraint("usermessage_user_id_fkey", "usermessage", type_="foreignkey")
    op.drop_constraint(
        "usermessage_notice_id_fkey",
        "usermessage",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_usermessage_template_id_sitemessagetemplate",
        "usermessage",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_usermessage_membership",
        "usermessage",
        "tenantmembership",
        ["user_id", "tenant_id"],
        ["user_id", "tenant_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_usermessage_notice_tenant",
        "usermessage",
        "notice",
        ["notice_id", "tenant_id"],
        ["id", "tenant_id"],
    )
    op.create_foreign_key(
        "fk_usermessage_template_tenant",
        "usermessage",
        "sitemessagetemplate",
        ["template_id", "tenant_id"],
        ["id", "tenant_id"],
    )


def downgrade() -> None:
    for table_name in ("usermessage", "notice", "sitemessagetemplate"):
        op.execute(
            sa.text(
                f"""
                DELETE FROM {table_name}
                WHERE tenant_id != CAST(:tenant_id AS UUID)
                """
            ).bindparams(tenant_id=DEFAULT_TENANT_ID)
        )

    op.drop_constraint(
        "fk_usermessage_template_tenant",
        "usermessage",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_usermessage_notice_tenant",
        "usermessage",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_usermessage_membership",
        "usermessage",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "usermessage_user_id_fkey",
        "usermessage",
        "user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "usermessage_notice_id_fkey",
        "usermessage",
        "notice",
        ["notice_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_usermessage_template_id_sitemessagetemplate",
        "usermessage",
        "sitemessagetemplate",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "uq_sitemessagetemplate_id_tenant_id",
        "sitemessagetemplate",
        type_="unique",
    )
    op.drop_constraint(
        "uq_sitemessagetemplate_tenant_code",
        "sitemessagetemplate",
        type_="unique",
    )
    op.drop_index(
        op.f("ix_sitemessagetemplate_code"),
        table_name="sitemessagetemplate",
    )
    op.create_index(
        op.f("ix_sitemessagetemplate_code"),
        "sitemessagetemplate",
        ["code"],
        unique=True,
    )
    op.drop_constraint(
        "uq_notice_id_tenant_id",
        "notice",
        type_="unique",
    )

    for table_name in ("usermessage", "sitemessagetemplate", "notice"):
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
