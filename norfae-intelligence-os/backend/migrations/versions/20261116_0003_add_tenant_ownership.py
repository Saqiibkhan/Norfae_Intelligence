"""add nullable tenant ownership to business data

Revision ID: 20261116_0003
Revises: 20261116_0002
Create Date: 2026-11-16

This is the safe expansion phase. Existing rows remain untouched and their
business_id stays NULL until the owner provisions a business through the
registration API and runs the explicit backfill workflow.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261116_0003"
down_revision: Union[str, None] = "20261116_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = (
    "analytics",
    "audit_logs",
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
    # All columns are nullable in this expansion revision. No record is
    # implicitly assigned to a tenant.
    for table in TABLES:
        op.add_column(table, sa.Column("business_id", sa.Integer(), nullable=True))
        ondelete = "SET NULL" if table == "audit_logs" else "CASCADE"
        op.create_foreign_key(
            f"fk_{table}_business_id_businesses",
            table,
            "businesses",
            ["business_id"],
            ["id"],
            ondelete=ondelete,
        )
        if table != "settings":
            op.create_index(f"ix_{table}_business_id", table, ["business_id"])

    op.create_unique_constraint("uq_settings_business_id", "settings", ["business_id"])

    # Replace global identifiers with tenant-aware uniqueness. PostgreSQL
    # retains multiple NULLs, so existing unassigned legacy rows remain valid.
    op.drop_index("ix_products_sku", table_name="products")
    op.create_index("ix_products_sku", "products", ["sku"], unique=False)
    op.create_unique_constraint("uq_products_business_sku", "products", ["business_id", "sku"])

    op.drop_index("ix_inventory_products_sku", table_name="inventory_products")
    op.create_index("ix_inventory_products_sku", "inventory_products", ["sku"], unique=False)
    op.create_unique_constraint("uq_inventory_products_business_sku", "inventory_products", ["business_id", "sku"])

    op.drop_constraint("expenses_external_reference_key", "expenses", type_="unique")
    op.create_unique_constraint(
        "uq_expenses_business_external_reference",
        "expenses",
        ["business_id", "external_reference"],
    )

    op.drop_constraint("categories_name_key", "categories", type_="unique")
    op.drop_constraint("categories_slug_key", "categories", type_="unique")
    op.create_unique_constraint("uq_categories_business_name", "categories", ["business_id", "name"])
    op.create_unique_constraint("uq_categories_business_slug", "categories", ["business_id", "slug"])

    op.drop_index("ix_meta_daily_stats_stats_date", table_name="meta_daily_stats")
    op.create_index("ix_meta_daily_stats_stats_date", "meta_daily_stats", ["stats_date"], unique=False)
    op.create_unique_constraint(
        "uq_meta_daily_stats_business_date", "meta_daily_stats", ["business_id", "stats_date"]
    )

    op.drop_index("ix_orders_internal_order_id", table_name="orders")
    op.create_index("ix_orders_internal_order_id", "orders", ["internal_order_id"], unique=False)
    op.create_unique_constraint(
        "uq_orders_business_internal_id", "orders", ["business_id", "internal_order_id"]
    )
    op.create_unique_constraint("uq_orders_business_id_id", "orders", ["business_id", "id"])
    op.create_unique_constraint(
        "uq_inventory_products_business_id_id", "inventory_products", ["business_id", "id"]
    )

    # Composite references prevent an order item from pointing at another
    # business's order or inventory product once the row has tenant ownership.
    op.drop_constraint("order_items_order_id_fkey", "order_items", type_="foreignkey")
    op.drop_constraint("order_items_inventory_product_id_fkey", "order_items", type_="foreignkey")
    op.create_foreign_key(
        "fk_order_items_business_order",
        "order_items",
        "orders",
        ["business_id", "order_id"],
        ["business_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_order_items_business_inventory",
        "order_items",
        "inventory_products",
        ["business_id", "inventory_product_id"],
        ["business_id", "id"],
    )


def downgrade() -> None:
    # Downgrading after tenant writes could merge distinct tenant identifiers
    # into old global uniqueness rules. Alembic will fail safely if duplicates
    # exist; operators must first export and reconcile tenant data.
    op.drop_constraint("fk_order_items_business_inventory", "order_items", type_="foreignkey")
    op.drop_constraint("fk_order_items_business_order", "order_items", type_="foreignkey")
    op.create_foreign_key(
        "order_items_order_id_fkey", "order_items", "orders", ["order_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "order_items_inventory_product_id_fkey", "order_items", "inventory_products", ["inventory_product_id"], ["id"]
    )

    op.drop_constraint("uq_inventory_products_business_id_id", "inventory_products", type_="unique")
    op.drop_constraint("uq_orders_business_id_id", "orders", type_="unique")
    op.drop_constraint("uq_orders_business_internal_id", "orders", type_="unique")
    op.drop_index("ix_orders_internal_order_id", table_name="orders")
    op.create_index("ix_orders_internal_order_id", "orders", ["internal_order_id"], unique=True)

    op.drop_constraint("uq_meta_daily_stats_business_date", "meta_daily_stats", type_="unique")
    op.drop_index("ix_meta_daily_stats_stats_date", table_name="meta_daily_stats")
    op.create_index("ix_meta_daily_stats_stats_date", "meta_daily_stats", ["stats_date"], unique=True)

    op.drop_constraint("uq_categories_business_slug", "categories", type_="unique")
    op.drop_constraint("uq_categories_business_name", "categories", type_="unique")
    op.create_unique_constraint("categories_name_key", "categories", ["name"])
    op.create_unique_constraint("categories_slug_key", "categories", ["slug"])

    op.drop_constraint("uq_expenses_business_external_reference", "expenses", type_="unique")
    op.create_unique_constraint("expenses_external_reference_key", "expenses", ["external_reference"])

    op.drop_constraint("uq_inventory_products_business_sku", "inventory_products", type_="unique")
    op.drop_index("ix_inventory_products_sku", table_name="inventory_products")
    op.create_index("ix_inventory_products_sku", "inventory_products", ["sku"], unique=True)

    op.drop_constraint("uq_products_business_sku", "products", type_="unique")
    op.drop_index("ix_products_sku", table_name="products")
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)

    op.drop_constraint("uq_settings_business_id", "settings", type_="unique")
    for table in reversed(TABLES):
        if table != "settings":
            op.drop_index(f"ix_{table}_business_id", table_name=table)
        op.drop_constraint(f"fk_{table}_business_id_businesses", table, type_="foreignkey")
        op.drop_column(table, "business_id")
