"""remove workflow module

Revision ID: 5f6a7b8c9d0e
Revises: 4e5f6a7b8c9d
Create Date: 2026-07-18 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op


revision: str = "5f6a7b8c9d0e"
down_revision: str | None = "4e5f6a7b8c9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM menu WHERE permission_code LIKE 'workflow:%'")
    op.execute("DELETE FROM menu WHERE route_path = '/workflows'")

    op.drop_table("workflownotification")
    op.drop_table("workflowcc")
    op.drop_table("workflowaudit")
    op.drop_table("workflowtask")
    op.drop_table("workflowinstance")
    op.drop_table("workflowdefinitionversion")
    op.drop_table("workflowdefinition")


def downgrade() -> None:
    raise NotImplementedError("The workflow module removal is destructive")
