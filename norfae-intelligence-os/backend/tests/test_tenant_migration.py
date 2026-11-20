from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.database import Base
import app.models


BACKEND_ROOT = Path(__file__).resolve().parents[1]
TENANT_TABLES = {
    "analytics",
    "assistant_conversations",
    "assistant_messages",
    "audit_logs",
    "categories",
    "creatives",
    "expenses",
    "expense_imports",
    "inventory_products",
    "meta_daily_stats",
    "meta_sync_state",
    "meta_sync_runs",
    "meta_ad_insights",
    "orders",
    "order_items",
    "products",
    "product_match_memory",
    "reports",
    "settings",
    "shopify_sync_state",
    "shopify_sync_runs",
}
REQUIRED_OWNER_TABLES = TENANT_TABLES - {"audit_logs"}


def test_tenant_models_have_business_id_and_required_tables_are_not_nullable():
    assert TENANT_TABLES <= set(Base.metadata.tables)
    for table_name in REQUIRED_OWNER_TABLES:
        assert Base.metadata.tables[table_name].c.business_id.nullable is False
    assert Base.metadata.tables["audit_logs"].c.business_id.nullable is True


def test_shopify_sync_metadata_contains_required_external_fields():
    assert "shopify_image_url" in Base.metadata.tables["products"].c
    assert "shopify_image_url" in Base.metadata.tables["inventory_products"].c
    assert "shopify_order_name" in Base.metadata.tables["orders"].c
    assert "shopify_total_refunded" in Base.metadata.tables["orders"].c
    assert "shopify_original_total_price" in Base.metadata.tables["orders"].c
    assert "trigger_type" in Base.metadata.tables["shopify_sync_runs"].c


def test_head_migration_enforces_ownership_after_nullable_expansion():
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    head = scripts.get_current_head()
    revision = scripts.get_revision(head)

    assert head == "20261122_0008"
    assert revision.down_revision == "20261121_0007"

    migration = (BACKEND_ROOT / "migrations/versions/20261116_0004_enforce_tenant_ownership.py").read_text()
    assert '"expenses"' in migration
    assert '"settings"' in migration
    assert '"audit_logs"' not in migration
    assert "WHERE business_id IS NULL" in migration
    assistant_migration = (BACKEND_ROOT / "migrations/versions/20261116_0005_add_assistant_conversations.py").read_text()
    assert '"assistant_conversations"' in assistant_migration
    assert '"assistant_messages"' in assistant_migration
    import_migration = (BACKEND_ROOT / "migrations/versions/20261120_0006_expense_csv_imports.py").read_text()
    assert '"expense_imports"' in import_migration
    shopify_migration = (BACKEND_ROOT / "migrations/versions/20261121_0007_shopify_sync.py").read_text()
    assert '"shopify_sync_runs"' in shopify_migration
    meta_migration = (BACKEND_ROOT / "migrations/versions/20261122_0008_meta_ads_insights.py").read_text()
    assert '"meta_sync_runs"' in meta_migration
    assert '"meta_ad_insights"' in meta_migration
