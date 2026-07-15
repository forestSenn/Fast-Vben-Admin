"""add tenant initialization templates

Revision ID: b8c9d1e2f3a4
Revises: a7b8c9d1e2f3
Create Date: 2026-07-15 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d1e2f3a4"
down_revision: str | None = "a7b8c9d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_TEMPLATE_ID = "00000000-0000-4000-8000-000000002001"


def upgrade() -> None:
    op.create_table(
        "tenantinitializationtemplate",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("root_department_code", sa.String(length=100), nullable=False),
        sa.Column("root_department_name", sa.String(length=100), nullable=False),
        sa.Column("seed_posts", sa.Boolean(), nullable=False),
        sa.Column("seed_dictionaries", sa.Boolean(), nullable=False),
        sa.Column("seed_settings", sa.Boolean(), nullable=False),
        sa.Column("seed_storage_channels", sa.Boolean(), nullable=False),
        sa.Column("seed_message_templates", sa.Boolean(), nullable=False),
        sa.Column("seed_sms_channels", sa.Boolean(), nullable=False),
        sa.Column("seed_mail_accounts", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tenantinitializationtemplate_code"),
        "tenantinitializationtemplate",
        ["code"],
        unique=True,
    )
    op.execute(
        sa.text(
            """
            INSERT INTO tenantinitializationtemplate (
                id, code, name, description,
                root_department_code, root_department_name,
                seed_posts, seed_dictionaries, seed_settings,
                seed_storage_channels, seed_message_templates,
                seed_sms_channels, seed_mail_accounts,
                is_default, is_active, created_at, updated_at
            ) VALUES (
                CAST(:template_id AS UUID), 'standard', 'Standard',
                'Default template matching the existing full tenant initialization.',
                'headquarters', '总部',
                TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE,
                TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """
        ).bindparams(template_id=DEFAULT_TEMPLATE_ID)
    )

    op.add_column(
        "tenant",
        sa.Column("initialization_template_id", sa.UUID(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE tenant SET initialization_template_id = CAST(:template_id AS UUID)"
        ).bindparams(template_id=DEFAULT_TEMPLATE_ID)
    )
    op.alter_column("tenant", "initialization_template_id", nullable=False)
    op.create_index(
        op.f("ix_tenant_initialization_template_id"),
        "tenant",
        ["initialization_template_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_tenant_initialization_template_id",
        "tenant",
        "tenantinitializationtemplate",
        ["initialization_template_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_tenant_initialization_template_id", "tenant", type_="foreignkey"
    )
    op.drop_index(op.f("ix_tenant_initialization_template_id"), table_name="tenant")
    op.drop_column("tenant", "initialization_template_id")
    op.drop_index(
        op.f("ix_tenantinitializationtemplate_code"),
        table_name="tenantinitializationtemplate",
    )
    op.drop_table("tenantinitializationtemplate")
