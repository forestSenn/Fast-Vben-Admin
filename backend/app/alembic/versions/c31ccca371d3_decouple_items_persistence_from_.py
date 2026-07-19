"""decouple items persistence from platform tables

Revision ID: c31ccca371d3
Revises: 44521cee7948
Create Date: 2026-07-20 01:21:32.777362

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'c31ccca371d3'
down_revision = '44521cee7948'
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("item"):
        op.drop_constraint("item_owner_id_fkey", "item", type_="foreignkey")
        op.drop_constraint("fk_item_tenant_id_tenant", "item", type_="foreignkey")
    op.create_foreign_key(
        "fk_socialuser_user_id_user",
        "socialuser",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_socialuser_social_client_id_socialclient",
        "socialuser",
        "socialclient",
        ["social_client_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_socialuser_social_client_id_socialclient", "socialuser", type_="foreignkey"
    )
    op.drop_constraint("fk_socialuser_user_id_user", "socialuser", type_="foreignkey")
    if sa.inspect(op.get_bind()).has_table("item"):
        op.create_foreign_key(
            "fk_item_tenant_id_tenant",
            "item",
            "tenant",
            ["tenant_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            "item_owner_id_fkey",
            "item",
            "user",
            ["owner_id"],
            ["id"],
            ondelete="CASCADE",
        )
