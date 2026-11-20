import threading
import time
import asyncio

import pytest
from sqlalchemy import text

from app.ai_engine.execution_budget import RequestBudgetExceeded, RequestExecutionBudget
from app.ai_engine.task_adapters import ProductTaskAdapter, TaskAdapterError
from app.agents.context import AgentContext
from app.core.database import SessionLocal
from app.core.tenant_context import get_current_business_id, tenant_scope
from app.models import Business, Product, User
from app.schemas.intelligence_schema import ProductIntelligencePage
from app.services.product_intelligence_service import ProductIntelligenceService
from app.core.config import settings
from app.schemas.coordination_schema import CoordinationTask


def test_request_budgets_are_isolated_and_bound_task_attempts(monkeypatch):
    monkeypatch.setattr(settings, "ASSISTANT_MAX_TASK_ATTEMPTS", 1)
    monkeypatch.setattr(settings, "ASSISTANT_MAX_LLM_CALLS", 1)
    first = RequestExecutionBudget("first")
    second = RequestExecutionBudget("second")
    task = CoordinationTask(task_id="products", domain="products")
    assert first.begin_task_attempt(task, {}) == 1
    first.finish_task_attempt(task.task_id, "succeeded")
    with pytest.raises(RequestBudgetExceeded):
        first.begin_task_attempt(task, {})
    first.reserve_llm_call()
    with pytest.raises(RequestBudgetExceeded):
        first.reserve_llm_call()
    assert second.total_attempts == second.llm_calls == 0
    assert first.task_traces[0]["attempt_count"] == 1
    assert first.task_traces[0]["attempts"][0]["duration_ms"] >= 0


def _page(business_id):
    return ProductIntelligencePage(
        business_id=business_id, start_date=None, end_date=None, total_products=0,
        page=1, page_size=10, best_performing_product_id=None,
        lowest_performing_product_id=None, products=[], warnings=[],
    )


def _seed_two_businesses(api_client):
    with api_client.session_factory() as db:
        users = [User(email=f"worker-{n}@example.com", password_hash="x") for n in (1, 2)]
        db.add_all(users)
        db.flush()
        businesses = [Business(name=f"Business {n}", owner_id=user.id) for n, user in enumerate(users, 1)]
        db.add_all(businesses)
        db.flush()
        ids = [business.id for business in businesses]
        for business_id, sku in zip(ids, ("A", "B")):
            with tenant_scope(business_id):
                db.add(Product(name=sku, sku=sku, business_id=business_id))
                db.flush()
        db.commit()
        return ids


def _worker_context(db):
    return AgentContext(
        user_id="9", business_id="47", permissions=frozenset({"analytics:read"}),
        dependencies={"db": db},
    )


@pytest.mark.anyio
async def test_worker_owns_session_and_preserves_tenant_scope(monkeypatch, api_client):
    business_ids = _seed_two_businesses(api_client)
    request_db = api_client.session_factory()
    original_factory = SessionLocal
    worker_sessions = []
    close_records = []
    session_threads = {}

    def tracking_factory(**kwargs):
        session = original_factory(**kwargs)
        worker_sessions.append(session)
        session_threads[id(session)] = threading.get_ident()
        original_close = session.close

        def close_once():
            close_records.append((id(session), threading.get_ident()))
            original_close()

        session.close = close_once
        return session

    monkeypatch.setattr("app.ai_engine.task_adapters.SessionLocal", tracking_factory)
    observed = {}

    def query_tenant(db, business_id, *_args, **_kwargs):
        observed.update(
            db=db, business_id=business_id,
            tenant=get_current_business_id(),
            products=[row.sku for row in db.query(Product).all()],
            thread=threading.get_ident(),
        )
        return _page(business_id)

    monkeypatch.setattr(ProductIntelligenceService, "analyze_business", query_tenant)
    task = CoordinationTask(task_id="products", domain="products")
    try:
        output = await ProductTaskAdapter().execute(task, _worker_context(request_db))
        assert output.products.business_id == 47
        assert observed["db"] is not request_db
        assert observed["business_id"] == 47
        assert observed["tenant"] == 47
        assert observed["products"] == []  # tenant 47 cannot see either other business
        # A worker scoped to business A can see A but not B.
        context = _worker_context(request_db)
        context = AgentContext(
            user_id="9", business_id=str(business_ids[0]),
            permissions=frozenset({"analytics:read"}), dependencies={"db": request_db},
        )
        await ProductTaskAdapter().execute(task, context)
        assert observed["products"] == ["A"]
        assert observed["thread"] == session_threads[id(observed["db"])]
        assert len(worker_sessions) == 2
        assert len(close_records) == 2
        assert close_records == [
            (id(session), session_threads[id(session)]) for session in worker_sessions
        ]
        # Explicit cross-business filter is still constrained by the loader criteria.
        with tenant_scope(business_ids[0]):
            assert [p.sku for p in request_db.query(Product).filter(
                Product.business_id == business_ids[1]
            ).all()] == []
    finally:
        request_db.close()


@pytest.mark.anyio
async def test_failure_rolls_back_and_closes_worker_session_once(monkeypatch, api_client):
    request_db = api_client.session_factory()
    original_factory = SessionLocal
    workers, closes = [], []

    def tracking_factory(**kwargs):
        session = original_factory(**kwargs)
        workers.append(session)
        original_close = session.close
        session.close = lambda: (closes.append(id(session)), original_close())[-1]
        return session

    monkeypatch.setattr("app.ai_engine.task_adapters.SessionLocal", tracking_factory)

    def fail_after_write(db, business_id, *_args, **_kwargs):
        db.add(Product(name="must roll back", sku="ROLLBACK", business_id=business_id))
        db.flush()
        raise RuntimeError("private database details")

    monkeypatch.setattr(ProductIntelligenceService, "analyze_business", fail_after_write)
    try:
        with pytest.raises(TaskAdapterError) as error:
            await ProductTaskAdapter().execute(
                CoordinationTask(task_id="products", domain="products"),
                _worker_context(request_db),
            )
        assert error.value.category == "INTERNAL_ERROR"
        assert len(workers) == len(closes) == 1
        assert request_db.query(Product).filter_by(sku="ROLLBACK").count() == 0
    finally:
        request_db.close()


@pytest.mark.anyio
async def test_timeout_and_request_cancellation_join_database_worker(monkeypatch, api_client):
    request_db = api_client.session_factory()
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    original_factory = SessionLocal
    workers, closes = [], []

    def tracking_factory(**kwargs):
        session = original_factory(**kwargs)
        workers.append(session)
        original_close = session.close
        session.close = lambda: (closes.append(id(session)), original_close())[-1]
        return session

    monkeypatch.setattr("app.ai_engine.task_adapters.SessionLocal", tracking_factory)

    def database_wait(db, business_id, *_args, **_kwargs):
        connection = db.connection().connection.driver_connection
        connection.create_function("hold_for_test", 0, lambda: (started.set(), release.wait(3), 1)[-1])
        db.execute(text("select hold_for_test()" )).scalar()
        finished.set()
        return _page(business_id)

    monkeypatch.setattr(ProductIntelligenceService, "analyze_business", database_wait)
    task = CoordinationTask(task_id="products", domain="products")
    try:
        for timeout_attempt in range(2):
            timeout_task = asyncio.create_task(ProductTaskAdapter().execute(
                task, _worker_context(request_db), timeout_seconds=0.01,
            ))
            assert await asyncio.to_thread(started.wait, 1)
            await asyncio.sleep(0.03)
            assert not timeout_task.done()
            release.set()
            with pytest.raises(TaskAdapterError) as timeout_error:
                await timeout_task
            assert timeout_error.value.category == "TIMEOUT"
            assert finished.is_set()
            assert len(closes) == timeout_attempt + 1
            if timeout_attempt == 0:
                started.clear(); release.clear(); finished.clear()

        started.clear(); release.clear(); finished.clear()
        cancel_task = asyncio.create_task(ProductTaskAdapter().execute(task, _worker_context(request_db)))
        assert await asyncio.to_thread(started.wait, 1)
        cancel_task.cancel()
        await asyncio.sleep(0.03)
        assert not cancel_task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await cancel_task
        assert finished.is_set()
        assert len(closes) == 3
        assert request_db.execute(text("select 1")).scalar() == 1
    finally:
        release.set()
        request_db.close()


@pytest.mark.anyio
async def test_task_timeout_waits_for_worker_before_returning(monkeypatch, api_client):
    worker_finished = threading.Event()
    adapter = ProductTaskAdapter()

    def slow_worker(*_args, **_kwargs):
        time.sleep(0.08)
        worker_finished.set()
        return {}

    monkeypatch.setattr(adapter, "run_sync", slow_worker)
    context = AgentContext(
        user_id="9", business_id="47", permissions=frozenset({"analytics:read"}),
        dependencies={"db": api_client.session_factory()},
    )
    started = time.monotonic()
    with pytest.raises(TaskAdapterError) as error:
        await adapter.execute(
            CoordinationTask(task_id="products", domain="products"), context,
            timeout_seconds=0.01,
        )
    assert error.value.category == "TIMEOUT"
    assert worker_finished.is_set()
    assert time.monotonic() - started >= 0.07
