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
    "inventory_products",
    "meta_daily_stats",
    "orders",
    "order_items",
    "products",
    "product_match_memory",
    "reports",
    "settings",
}
REQUIRED_OWNER_TABLES = TENANT_TABLES - {"audit_logs"}


def test_tenant_models_have_business_id_and_required_tables_are_not_nullable():
    assert TENANT_TABLES <= set(Base.metadata.tables)
    for table_name in REQUIRED_OWNER_TABLES:
        assert Base.metadata.tables[table_name].c.business_id.nullable is False
    assert Base.metadata.tables["audit_logs"].c.business_id.nullable is True


def test_head_migration_enforces_ownership_after_nullable_expansion():
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    head = scripts.get_current_head()
    revision = scripts.get_revision(head)

    assert head == "20261116_0005"
    assert revision.down_revision == "20261116_0004"

    migration = (BACKEND_ROOT / "migrations/versions/20261116_0004_enforce_tenant_ownership.py").read_text()
    assert '"expenses"' in migration
    assert '"settings"' in migration
    assert '"audit_logs"' not in migration
    assert "WHERE business_id IS NULL" in migration
    assistant_migration = (BACKEND_ROOT / "migrations/versions/20261116_0005_add_assistant_conversations.py").read_text()
    assert '"assistant_conversations"' in assistant_migration
    assert '"assistant_messages"' in assistant_migration
