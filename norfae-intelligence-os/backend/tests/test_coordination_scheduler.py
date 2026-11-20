from datetime import date

import pytest
from pydantic import ValidationError

from app.ai_engine.business_assistant_graph import build_coordination_plan
from app.ai_engine.coordination_scheduler import next_ready_task
from app.ai_engine.execution_budget import RequestBudgetExceeded, RequestExecutionBudget
from app.ai_engine.finding_extraction import extract_findings
from app.ai_engine.task_adapters import ProfitabilityTaskOutput
from app.schemas.coordination_schema import (
    AgentFinding,
    CoordinationPlan,
    CoordinationTask,
    FindingRequirement,
    ReportingPeriod,
    SharedFindingsContext,
    TaskResult,
)
from app.schemas.intelligence_schema import ProfitabilityComponent, ProfitabilitySummary
from app.core.config import settings


PERIOD = ReportingPeriod(start_date="2026-08-01", end_date="2026-08-31")
TREND_ID = "profitability:net_profit_trend"


def _summary(start, end, profit, *, available=True, complete=True):
    component = ProfitabilityComponent(amount=profit, available=available)
    return ProfitabilitySummary(
        business_id=1,
        start_date=start,
        end_date=end,
        orders_inspected=10,
        delivered_orders=10,
        cancelled_orders=0,
        returned_orders=0,
        other_status_orders=0,
        gross_revenue=component,
        discounts=component,
        refunds=component,
        net_revenue=component,
        cost_of_goods_sold=component,
        packaging_cost=component,
        delivery_cost=component,
        advertising_expense=component,
        other_business_expenses=component,
        net_profit=component,
        profit_margin_percent=None,
        complete=complete,
        warnings=[],
    )


def _profit_output(current_profit, previous_profit, *, current_available=True, previous_available=True):
    return ProfitabilityTaskOutput(
        profitability=_summary(date(2026, 9, 1), date(2026, 9, 30), current_profit,
                               available=current_available),
        previous_period_profitability=_summary(date(2026, 8, 2), date(2026, 8, 31), previous_profit,
                                               available=previous_available),
        product_profitability=[],
    )


def _task(task_id, *, domain, dependencies=(), optional=(), requirements=()):
    return CoordinationTask(
        task_id=task_id,
        domain=domain,
        dependency_task_ids=list(dependencies),
        optional_dependency_task_ids=list(optional),
        finding_requirements=list(requirements),
        parameters={"start_date": "2026-09-01", "end_date": "2026-09-30"}
        if domain != "data_quality" else {},
    )


def _investigation_plan(*, optional=False):
    root = _task("profitability", domain="profitability")
    child = _task(
        "products",
        domain="products",
        dependencies=["profitability"],
        optional=["profitability"] if optional else [],
        requirements=[FindingRequirement(
            source_task_id="profitability", finding_id=TREND_ID,
        )],
    )
    return CoordinationPlan(plan_id="plan", tasks=[root, child], status="running")


def _complete_root(plan, *, finding=None, failed=False):
    root_status = "failed" if failed else "succeeded"
    plan = plan.model_copy(update={
        "tasks": [plan.tasks[0].model_copy(update={"status": root_status}), plan.tasks[1]],
    })
    result = TaskResult(
        task_id="profitability", domain="profitability", status=root_status,
        result=None if failed else {"profitability": {}},
        safe_error_code="task_execution_failed" if failed else None,
        finding_ids=[finding.finding_id] if finding else [],
    )
    shared = SharedFindingsContext().with_task_result(result)
    if finding:
        shared = shared.with_finding(finding)
    return plan, shared


def test_finding_extraction_preserves_zero_null_period_and_provenance():
    findings = extract_findings("profitability", "profitability", _profit_output(0, 0))
    current, previous, trend = findings
    assert current.value == 0
    assert current.evidence_status == "verified"
    assert current.reporting_period == ReportingPeriod(start_date="2026-09-01", end_date="2026-09-30")
    assert current.source_service == "DeterministicProfitabilityService.overall"
    assert current.evidence_ref == "profitability"
    assert trend.value["status"] == "comparable"
    assert trend.value["direction"] == "unchanged"
    assert trend.value["current_period_start"] == "2026-09-01"
    assert trend.value["previous_period_start"] == "2026-08-02"
    assert trend.value["percentage_change"] is None
    assert previous.reporting_period == ReportingPeriod(start_date="2026-08-02", end_date="2026-08-31")

    missing = extract_findings(
        "profitability", "profitability",
        _profit_output(None, 5, current_available=False, previous_available=True),
    )
    assert missing[0].value is None
    assert missing[0].evidence_status == "unavailable"
    assert missing[2].value is None
    assert missing[2].evidence_status == "unavailable"


def test_extracted_profitability_decline_is_deterministic_and_period_bound():
    findings = extract_findings("profitability", "profitability", _profit_output(4, 9))
    trend = findings[2]
    assert trend.value["direction"] == "decrease"
    assert trend.value["current_value"] == 4.0
    assert trend.value["previous_value"] == 9.0
    assert trend.value["absolute_change"] == -5.0
    assert trend.value["percentage_change"] == -55.56
    assert trend.value["current_period_end"] == "2026-09-30"
    assert trend.value["previous_period_end"] == "2026-08-31"
    assert trend.evidence_status == "verified"
    assert "does not establish a cause" in trend.limitations[-1]


def test_sequential_scheduler_runs_prerequisites_then_passes_only_declared_findings():
    plan = _investigation_plan()
    plan, shared, task_id, context = next_ready_task(plan, SharedFindingsContext())
    assert task_id == "profitability"
    assert context.findings == []

    decline = extract_findings("profitability", "profitability", _profit_output(4, 9))[2]
    plan, shared = _complete_root(plan, finding=decline)
    plan, shared, task_id, context = next_ready_task(plan, shared)
    assert task_id == "products"
    assert [finding.finding_id for finding in context.findings] == [TREND_ID]
    assert context.unavailable_finding_ids == []
    assert plan.tasks[1].status == "running"
    # A running/completed task is never selected a second time.
    plan, shared, duplicate_task_id, _ = next_ready_task(plan, shared)
    assert duplicate_task_id is None


def test_required_failed_dependency_skips_task_and_records_reason():
    plan, shared = _complete_root(_investigation_plan(), failed=True)
    plan, shared, task_id, context = next_ready_task(plan, shared)
    assert task_id is None
    assert plan.tasks[1].status == "skipped"
    assert shared.task_results["products"].safe_error_code == "dependency_failed"


@pytest.mark.parametrize("optional", [False, True])
def test_pending_dependency_blocks_dependent_task(optional):
    plan = _investigation_plan(optional=optional)
    plan, shared, first_task, _ = next_ready_task(plan, SharedFindingsContext())
    assert first_task == "profitability"
    # The first task is now running. Neither required nor optional dependencies
    # are terminal, so the dependent cannot run or be marked unavailable yet.
    plan, shared, task_id, context = next_ready_task(plan, shared)
    assert task_id is None
    assert plan.tasks[1].status == "pending"
    assert shared.task_results == {}
    assert context.findings == []
    assert context.unavailable_finding_ids == []


def test_optional_success_passes_declared_finding_only():
    plan = _investigation_plan(optional=True)
    decline = extract_findings("profitability", "profitability", _profit_output(4, 9))[2]
    plan, shared = _complete_root(plan, finding=decline)
    plan, shared, task_id, context = next_ready_task(plan, shared)
    assert task_id == "products"
    assert context.findings == [decline]
    assert context.unavailable_finding_ids == []


def test_optional_skipped_dependency_allows_execution_with_unavailable_finding():
    plan = _investigation_plan(optional=True)
    plan = plan.model_copy(update={
        "tasks": [plan.tasks[0].model_copy(update={"status": "skipped"}), plan.tasks[1]],
    })
    shared = SharedFindingsContext().with_task_result(TaskResult(
        task_id="profitability", domain="profitability", status="skipped",
        safe_error_code="investigation_not_warranted", attempt_count=0,
    ))
    plan, shared, task_id, context = next_ready_task(plan, shared)
    assert task_id == "products"
    assert context.findings == []
    assert context.unavailable_finding_ids == [TREND_ID]


def test_multiple_optional_dependencies_wait_then_share_success_only():
    trend = extract_findings("profitability", "profitability", _profit_output(4, 9))[2]
    profitability = _task("profitability", domain="profitability")
    products = _task("products", domain="products")
    dependent = _task(
        "cities", domain="cities", dependencies=["profitability", "products"],
        optional=["profitability", "products"], requirements=[
            FindingRequirement(source_task_id="profitability", finding_id=TREND_ID),
            FindingRequirement(source_task_id="products", finding_id="products:revenue"),
        ],
    )
    plan = CoordinationPlan(plan_id="multi-optional", tasks=[profitability, products, dependent])
    plan = plan.model_copy(update={"tasks": [
        profitability.model_copy(update={"status": "succeeded"}),
        products.model_copy(update={"status": "running"}), dependent,
    ]})
    shared = SharedFindingsContext().with_finding(trend).with_task_result(TaskResult(
        task_id="profitability", domain="profitability", status="succeeded",
        result={"profitability": {}}, finding_ids=[TREND_ID],
    ))
    plan, shared, task_id, _ = next_ready_task(plan, shared)
    assert task_id is None  # second optional prerequisite is still running
    plan = plan.model_copy(update={"tasks": [plan.tasks[0],
                                               plan.tasks[1].model_copy(update={"status": "failed"}),
                                               plan.tasks[2]]})
    shared = shared.with_task_result(TaskResult(
        task_id="products", domain="products", status="failed",
        safe_error_code="task_execution_failed",
    ))
    plan, shared, task_id, context = next_ready_task(plan, shared)
    assert task_id == "cities"
    assert [finding.finding_id for finding in context.findings] == [TREND_ID]
    assert context.unavailable_finding_ids == ["products:revenue"]


def test_waiting_for_dependencies_does_not_consume_execution_budget(monkeypatch):
    monkeypatch.setattr(settings, "ASSISTANT_MAX_TASK_ATTEMPTS", 1)
    plan = _investigation_plan(optional=True)
    root = plan.tasks[0]
    budget = RequestExecutionBudget("waiting")
    budget.begin_task_attempt(root, {})
    plan = plan.model_copy(update={"tasks": [
        root.model_copy(update={"status": "running"}), plan.tasks[1],
    ]})
    plan, shared, task_id, _ = next_ready_task(plan, SharedFindingsContext())
    assert task_id is None
    assert budget.total_attempts == 1
    with pytest.raises(RequestBudgetExceeded):
        budget.begin_task_attempt(plan.tasks[1], {"profitability": "running"})


def test_optional_failed_dependency_runs_with_explicit_unavailable_finding():
    plan, shared = _complete_root(_investigation_plan(optional=True), failed=True)
    plan, shared, task_id, context = next_ready_task(plan, shared)
    assert task_id == "products"
    assert context.findings == []
    assert context.unavailable_finding_ids == [TREND_ID]


def test_optional_missing_finding_is_explicit_even_when_dependency_succeeded():
    plan, shared = _complete_root(_investigation_plan(optional=True))
    plan, shared, task_id, context = next_ready_task(plan, shared)
    assert task_id == "products"
    assert context.findings == []
    assert context.unavailable_finding_ids == [TREND_ID]


def test_missing_finding_is_passed_as_unavailable_instead_of_invented():
    plan, shared = _complete_root(_investigation_plan())
    plan, shared, task_id, context = next_ready_task(plan, shared)
    assert task_id == "products"
    assert plan.tasks[1].status == "running"
    assert context.findings == []
    assert context.unavailable_finding_ids == [TREND_ID]


@pytest.mark.parametrize("direction", ["increase", None])
def test_investigation_plan_skips_followups_without_supported_decline(direction):
    plan, domains, investigation = build_coordination_plan(
        intent="profitability", requested_domains=["creatives"],
        question="Why did profitability decrease?", start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30), execution_id="execution",
    )
    assert investigation is True
    assert domains == ["profitability", "products", "cities", "marketing", "anomalies"]
    assert all(task.dependency_task_ids == ["profitability"] for task in plan.tasks[1:])
    trend = AgentFinding(
        finding_id=TREND_ID, domain="profitability", name="net_profit_trend",
        value=(None if direction is None else {"direction": direction}),
        reporting_period=PERIOD, source_service="DeterministicProfitabilityService.overall",
        evidence_ref="profitability",
        evidence_status="unavailable" if direction is None else "verified",
    )
    # A completed root result must claim the finding before the scheduler will trust it.
    plan, shared = _complete_root(plan, finding=trend)
    plan, shared, task_id, _ = next_ready_task(plan, shared, profitability_investigation=True)
    assert task_id is None
    assert all(task.status == "skipped" for task in plan.tasks[1:])
    assert all(shared.task_results[task.task_id].safe_error_code == "investigation_not_warranted"
               for task in plan.tasks[1:])


def test_non_investigation_profitability_plan_does_not_add_followups():
    plan, domains, investigation = build_coordination_plan(
        intent="profitability", requested_domains=[], question="Tell me about profitability",
        start_date=date(2026, 9, 1), end_date=date(2026, 9, 30), execution_id="simple",
    )
    assert investigation is False
    assert domains == ["profitability"]
    assert len(plan.tasks) == 1


def test_plan_rejects_invalid_finding_reference_and_shared_context_blocks_duplicate_tasks():
    with pytest.raises(ValidationError, match="declared dependency"):
        CoordinationPlan(plan_id="bad", tasks=[
            _task("profitability", domain="profitability"),
            _task("products", domain="products", requirements=[FindingRequirement(
                source_task_id="profitability", finding_id=TREND_ID,
            )]),
        ])
    result = TaskResult(task_id="profitability", domain="profitability", status="succeeded", result={})
    shared = SharedFindingsContext().with_task_result(result)
    with pytest.raises(ValueError, match="more than once"):
        shared.with_task_result(result)


def test_findings_are_isolated_between_request_contexts():
    finding = extract_findings("profitability", "profitability", _profit_output(0, 0))[0]
    request_a = SharedFindingsContext().with_finding(finding)
    request_b = SharedFindingsContext()
    assert finding.finding_id in request_a.findings
    assert request_b.findings == {}
