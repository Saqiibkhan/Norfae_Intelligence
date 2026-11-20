"""enforce ownership on business tables after explicit legacy backfill

Revision ID: 20261116_0004
Revises: 20261116_0003
Create Date: 2026-11-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261116_0004"
down_revision: Union[str, None] = "20261116_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BUSINESS_TABLES = (
    "analytics",
    "categories",
    "creatives",
    "expenses",
    "inventory_products",
    "meta_daily_stats",
    "orders",
    "order_items",
    "products",
    "product_match_memory",
    "reports",
    "settings",
)


def upgrade() -> None:
    if not op.get_context().as_sql:
        bind = op.get_bind()
        for table in BUSINESS_TABLES:
            unassigned = bind.execute(
                sa.text(f"SELECT count(*) FROM {table} WHERE business_id IS NULL")
            ).scalar_one()
            if unassigned:
                raise RuntimeError(
                    f"Cannot enforce tenant ownership: {table} still has {unassigned} unassigned rows."
                )

    for table in BUSINESS_TABLES:
        op.alter_column(
            table,
            "business_id",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade() -> None:
    for table in reversed(BUSINESS_TABLES):
        op.alter_column(
            table,
            "business_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
