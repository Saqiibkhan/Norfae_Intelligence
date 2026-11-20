"""add tenant and user scoped expense import previews and history

Revision ID: 20261120_0006
Revises: 20261116_0005
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261120_0006"
down_revision: Union[str, None] = "20261116_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "expense_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mapping_json", sa.Text(), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=False),
        sa.Column("rows_json", sa.Text(), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("imported_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_rows", sa.Integer(), nullable=False),
        sa.Column("duplicate_rows", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_expense_imports_business_id", "expense_imports", ["business_id"])
    op.create_index("ix_expense_imports_user_id", "expense_imports", ["user_id"])
    op.create_index("ix_expense_imports_business_user_created", "expense_imports", ["business_id", "user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("expense_imports")
