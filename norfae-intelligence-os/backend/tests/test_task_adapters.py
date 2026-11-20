from datetime import date

import pytest

from app.agents.context import AgentContext
from app.ai_engine.task_adapters import (
    DuplicateTaskAdapterError,
    AnomalyTaskAdapter,
    ProductTaskAdapter,
    TaskAdapterError,
    TaskAdapterRegistry,
)
from app.schemas.coordination_schema import CoordinationTask
from app.schemas.coordination_schema import AgentFinding, FindingRequirement, TaskExecutionContext
from app.schemas.intelligence_schema import ProductIntelligencePage
from app.services.product_intelligence_service import ProductIntelligenceService


def _context(*, business_id="47", permissions=frozenset({"analytics:read"}), dependencies=None):
    return AgentContext(
        user_id="9",
        business_id=business_id,
        permissions=permissions,
        dependencies=dependencies if dependencies is not None else {"db": object()},
    )


def test_registry_is_fixed_and_contains_every_supported_domain():
    registry = TaskAdapterRegistry()
    assert {"profitability", "products", "cities", "marketing", "creatives", "anomalies", "data_quality"} == {
        *registry.domains
    }
    with pytest.raises(TaskAdapterError) as error:
        registry.get_adapter("run_arbitrary_function")
    assert error.value.category == "UNSUPPORTED_DOMAIN"


def test_registry_rejects_duplicate_domains():
    registry = TaskAdapterRegistry(adapters=[])
    adapter = ProductTaskAdapter()
    registry.register(adapter)
    with pytest.raises(DuplicateTaskAdapterError):
        registry.register(ProductTaskAdapter())


@pytest.mark.anyio
async def test_adapter_validates_parameters_and_enforces_authenticated_permission():
    adapter = ProductTaskAdapter()
    malformed_task = CoordinationTask.model_construct(
        task_id="products", domain="products", priority=3,
        dependency_task_ids=[], status="pending", parameters={"page_size": 1000},
    )
    with pytest.raises(TaskAdapterError) as error:
        await adapter.execute(malformed_task, _context())
    assert error.value.category == "VALIDATION_ERROR"

    valid_task = CoordinationTask(task_id="products", domain="products")
    with pytest.raises(TaskAdapterError) as error:
        await adapter.execute(valid_task, _context(permissions=frozenset()))
    assert error.value.category == "PERMISSION_DENIED"


@pytest.mark.anyio
async def test_adapter_rejects_missing_or_undeclared_finding_references():
    adapter = ProductTaskAdapter()
    task = CoordinationTask(
        task_id="products", domain="products", dependency_task_ids=["profitability"],
        finding_requirements=[FindingRequirement(
            source_task_id="profitability", finding_id="profitability:net_profit_trend",
        )],
    )
    with pytest.raises(TaskAdapterError) as error:
        await adapter.execute(task, _context())
    assert error.value.category == "INVALID_TASK"

    undeclared = AgentFinding(
        finding_id="cities:revenue", domain="cities", name="revenue", value=10,
        source_service="CityIntelligenceService.analyze_business", evidence_ref="cities",
        evidence_status="verified",
    )
    with pytest.raises(TaskAdapterError) as error:
        await ProductTaskAdapter().execute(
            CoordinationTask(task_id="products", domain="products"), _context(),
            TaskExecutionContext(findings=[undeclared]),
        )
    assert error.value.category == "INVALID_TASK"


@pytest.mark.anyio
async def test_adapter_requires_approved_database_dependency():
    task = CoordinationTask(task_id="products", domain="products")
    with pytest.raises(TaskAdapterError) as error:
        await ProductTaskAdapter().execute(task, _context(dependencies={}))
    assert error.value.category == "DATA_UNAVAILABLE"


@pytest.mark.anyio
async def test_anomaly_adapter_requires_approved_service_dependency():
    task = CoordinationTask(task_id="anomalies", domain="anomalies")
    with pytest.raises(TaskAdapterError) as error:
        await AnomalyTaskAdapter().execute(task, _context())
    assert error.value.category == "DATA_UNAVAILABLE"


@pytest.mark.anyio
async def test_adapter_uses_only_authenticated_tenant_and_validates_output(monkeypatch, api_client):
    seen = {}

    def analyze(db, business_id, start_date, end_date, page, page_size):
        seen.update({"db": db, "business_id": business_id, "start_date": start_date, "end_date": end_date})
        return ProductIntelligencePage(
            business_id=business_id,
            start_date=start_date,
            end_date=end_date,
            total_products=0,
            page=page,
            page_size=page_size,
            best_performing_product_id=None,
            lowest_performing_product_id=None,
            products=[],
            warnings=[],
        )

    db = api_client.session_factory()
    monkeypatch.setattr(ProductIntelligenceService, "analyze_business", analyze)
    task = CoordinationTask(
        task_id="products", domain="products",
        parameters={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    output = await ProductTaskAdapter().execute(task, _context(dependencies={"db": db}))
    assert output.products.business_id == 47
    assert seen == {
        "db": seen["db"],
        "business_id": 47,
        "start_date": date(2026, 9, 1),
        "end_date": date(2026, 9, 30),
    }

    monkeypatch.setattr(ProductIntelligenceService, "analyze_business", lambda *_a, **_k: {"invalid": True})
    with pytest.raises(TaskAdapterError) as error:
        await ProductTaskAdapter().execute(task, _context(dependencies={"db": db}))
    assert error.value.category == "VALIDATION_ERROR"
    db.close()


@pytest.mark.anyio
async def test_adapter_errors_are_safe_and_categorized(monkeypatch, api_client):
    def fail(*_args, **_kwargs):
        raise RuntimeError("database password and SQL must not escape")

    monkeypatch.setattr(ProductIntelligenceService, "analyze_business", fail)
    task = CoordinationTask(task_id="products", domain="products")
    with pytest.raises(TaskAdapterError) as error:
        await ProductTaskAdapter().execute(
            task, _context(dependencies={"db": api_client.session_factory()})
        )
    assert error.value.category == "INTERNAL_ERROR"
    assert "password" not in str(error.value)
    assert "SQL" not in str(error.value)
