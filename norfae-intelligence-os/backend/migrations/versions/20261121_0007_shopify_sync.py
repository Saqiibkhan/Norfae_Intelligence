"""add Shopify external identities and sync state/history

Revision ID: 20261121_0007
Revises: 20261120_0006
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261121_0007"
down_revision: Union[str, None] = "20261120_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for table, column in (
        ("inventory_products", "shopify_variant_id"),
        ("orders", "shopify_order_id"),
    ):
        duplicates = bind.execute(sa.text(
            f"SELECT business_id, {column}, count(*) FROM {table} "
            f"WHERE {column} IS NOT NULL GROUP BY business_id, {column} HAVING count(*) > 1 LIMIT 1"
        )).first()
        if duplicates:
            raise RuntimeError(f"Cannot add Shopify identity constraint: duplicate {table}.{column} exists for a business.")

    # Shopify identities remain nullable for all existing manually entered data.
    for name, sql_type in (
        ("shopify_product_id", sa.String()), ("shopify_variant_id", sa.String()),
        ("shopify_sku", sa.String()), ("shopify_status", sa.String()),
        ("shopify_updated_at", sa.DateTime()),
        ("shopify_created_at", sa.DateTime()), ("shopify_description", sa.String()),
        ("shopify_vendor", sa.String()), ("shopify_compare_at_price", sa.Float()),
        ("shopify_image_url", sa.String(length=2048)),
    ):
        op.add_column("products", sa.Column(name, sql_type, nullable=True))
    for name, sql_type in (("shopify_sku", sa.String()), ("shopify_status", sa.String()),
                           ("shopify_updated_at", sa.DateTime()), ("shopify_created_at", sa.DateTime()),
                           ("shopify_compare_at_price", sa.Float())):
        op.add_column("inventory_products", sa.Column(name, sql_type, nullable=True))
    op.add_column("inventory_products", sa.Column("shopify_image_url", sa.String(length=2048), nullable=True))

    op.add_column("orders", sa.Column("shopify_order_name", sa.String(length=100), nullable=True))
    op.add_column("orders", sa.Column("shopify_total_refunded", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("shopify_updated_at", sa.DateTime(), nullable=True))
    op.add_column("orders", sa.Column("shopify_currency", sa.String(length=3), nullable=True))
    op.add_column("orders", sa.Column("shopify_financial_status", sa.String(length=40), nullable=True))
    op.add_column("orders", sa.Column("shopify_fulfillment_status", sa.String(length=40), nullable=True))
    op.add_column("orders", sa.Column("shopify_total_price", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("shopify_original_total_price", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("shopify_subtotal_price", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("shopify_total_discounts", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("shopify_total_tax", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("shopify_shipping_price", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("shopify_cancelled_at", sa.DateTime(), nullable=True))
    op.create_unique_constraint("uq_products_business_shopify_variant", "products", ["business_id", "shopify_variant_id"])
    op.create_unique_constraint("uq_inventory_business_shopify_variant", "inventory_products", ["business_id", "shopify_variant_id"])
    op.create_unique_constraint("uq_orders_business_shopify_order", "orders", ["business_id", "shopify_order_id"])
    op.add_column("order_items", sa.Column("shopify_line_item_id", sa.String(), nullable=True))
    op.add_column("order_items", sa.Column("shopify_product_id", sa.String(), nullable=True))
    op.add_column("order_items", sa.Column("shopify_variant_id", sa.String(), nullable=True))
    op.add_column("order_items", sa.Column("shopify_discount", sa.Float(), nullable=True))
    op.create_unique_constraint("uq_order_items_business_shopify_line", "order_items", ["business_id", "shopify_line_item_id"])

    op.create_table(
        "shopify_sync_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_domain", sa.String(length=255), nullable=True),
        sa.Column("products_cursor", sa.DateTime(), nullable=True),
        sa.Column("orders_cursor", sa.DateTime(), nullable=True),
        sa.Column("products_running_since", sa.DateTime(), nullable=True),
        sa.Column("orders_running_since", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("business_id", name="uq_shopify_sync_state_business"),
    )
    op.create_table(
        "shopify_sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sync_type", sa.String(length=20), nullable=False),
        sa.Column("trigger_type", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("records_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_category", sa.String(length=40), nullable=True),
        sa.Column("error_summary", sa.String(length=300), nullable=True),
        sa.Column("cursor_before", sa.DateTime(), nullable=True),
        sa.Column("cursor_after", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_shopify_sync_runs_business_id", "shopify_sync_runs", ["business_id"])
    op.create_index("ix_shopify_sync_runs_user_id", "shopify_sync_runs", ["user_id"])
    op.create_index("ix_shopify_sync_runs_business_started", "shopify_sync_runs", ["business_id", "started_at"])


def downgrade() -> None:
    op.drop_table("shopify_sync_runs")
    op.drop_table("shopify_sync_state")
    op.drop_constraint("uq_order_items_business_shopify_line", "order_items", type_="unique")
    op.drop_column("order_items", "shopify_variant_id")
    op.drop_column("order_items", "shopify_product_id")
    op.drop_column("order_items", "shopify_line_item_id")
    op.drop_constraint("uq_orders_business_shopify_order", "orders", type_="unique")
    for column in ("shopify_total_refunded", "shopify_original_total_price", "shopify_order_name", "shopify_cancelled_at", "shopify_shipping_price", "shopify_total_tax", "shopify_total_discounts", "shopify_subtotal_price",
                   "shopify_total_price", "shopify_fulfillment_status", "shopify_financial_status", "shopify_currency", "shopify_updated_at"):
        op.drop_column("orders", column)
    op.drop_constraint("uq_inventory_business_shopify_variant", "inventory_products", type_="unique")
    op.drop_constraint("uq_products_business_shopify_variant", "products", type_="unique")
    for column in ("shopify_image_url", "shopify_compare_at_price", "shopify_vendor", "shopify_description", "shopify_created_at", "shopify_updated_at", "shopify_status", "shopify_sku", "shopify_variant_id", "shopify_product_id"):
        op.drop_column("products", column)
    for column in ("shopify_image_url", "shopify_compare_at_price", "shopify_created_at", "shopify_updated_at", "shopify_status", "shopify_sku"):
        op.drop_column("inventory_products", column)
    op.drop_column("order_items", "shopify_discount")
