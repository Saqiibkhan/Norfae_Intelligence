from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.coordination_schema import (
    AgentFinding,
    CoordinationPlan,
    CoordinationTask,
    ReportingPeriod,
    SharedFindingsContext,
    TaskResult,
)


def _task(task_id, *, domain="profitability", dependencies=None, parameters=None):
    return CoordinationTask(
        task_id=task_id,
        domain=domain,
        dependency_task_ids=dependencies or [],
        parameters=parameters or {},
    )


def _plan(*tasks):
    return CoordinationPlan(plan_id="plan-test", tasks=list(tasks))


def test_valid_task_uses_domain_specific_existing_parameter_schema():
    task = _task("profit", parameters={"start_date": "2026-09-01", "end_date": "2026-09-30"})
    assert task.domain == "profitability"
    assert task.parameters == {"start_date": date(2026, 9, 1), "end_date": date(2026, 9, 30)}
    assert task.status == "pending"


def test_task_rejects_unknown_domains_and_invalid_parameters():
    with pytest.raises(ValidationError):
        _task("unknown", domain="arbitrary_tool")
    with pytest.raises(ValidationError):
        _task("bad-products", domain="products", parameters={"page_size": 1000})
    with pytest.raises(ValidationError):
        _task("bad-data-quality", domain="data_quality", parameters={"business_id": 123})


def test_plan_rejects_duplicate_task_ids():
    with pytest.raises(ValidationError, match="unique"):
        _plan(_task("same"), _task("same", domain="cities"))


def test_plan_rejects_missing_and_self_dependencies():
    with pytest.raises(ValidationError, match="missing dependency"):
        _plan(_task("a", dependencies=["not-present"]))
    with pytest.raises(ValidationError, match="cannot depend on itself"):
        _plan(_task("a", dependencies=["a"]))


def test_plan_rejects_circular_dependencies():
    with pytest.raises(ValidationError, match="cycles"):
        _plan(_task("a", dependencies=["b"]), _task("b", dependencies=["a"], domain="cities"))


def test_plan_enforces_task_count_limit():
    tasks = [_task(f"task-{index}", domain="profitability") for index in range(15)]
    with pytest.raises(ValidationError):
        _plan(*tasks)


def test_valid_finding_supports_provenance_and_evidence_status():
    finding = AgentFinding(
        finding_id="profit-margin-september",
        domain="profitability",
        name="gross_margin",
        value=0.42,
        reporting_period=ReportingPeriod(start_date="2026-09-01", end_date="2026-09-30"),
        source_service="deterministic_profitability",
        evidence_ref="profitability",
        evidence_status="verified",
        limitations=["Discounts are not represented."],
    )
    assert finding.value == 0.42
    assert finding.evidence_status == "verified"


def test_finding_rejects_invalid_period_value_and_unavailable_value():
    with pytest.raises(ValidationError):
        ReportingPeriod(start_date="2026-09-30", end_date="2026-09-01")
    with pytest.raises(ValidationError, match="JSON-compatible"):
        AgentFinding(
            finding_id="invalid-value", domain="products", name="metric", value=object(),
            source_service="product_intelligence", evidence_status="estimated",
        )
    with pytest.raises(ValidationError, match="cannot include a value"):
        AgentFinding(
            finding_id="unavailable", domain="cities", name="revenue", value=5,
            source_service="city_intelligence", evidence_status="unavailable",
        )
    with pytest.raises(ValidationError):
        AgentFinding(
            finding_id="extra-field", domain="cities", name="revenue", value=5,
            source_service="city_intelligence", evidence_status="verified", raw_error="secret",
        )


def test_shared_context_is_request_scoped_and_contains_only_typed_results():
    first_request = SharedFindingsContext()
    second_request = SharedFindingsContext()
    result = TaskResult(task_id="profit", domain="profitability", status="succeeded", result={"profit": 10})
    updated = first_request.with_task_result(result)

    assert first_request.task_results == {}
    assert second_request.task_results == {}
    assert updated.task_results == {"profit": result}
    with pytest.raises(ValidationError):
        SharedFindingsContext(business_id=123)
    with pytest.raises(ValidationError):
        SharedFindingsContext(db=object())


def test_task_result_requires_safe_status_consistent_error_and_result():
    with pytest.raises(ValidationError):
        TaskResult(task_id="bad", domain="products", status="failed", safe_error_code="provider detail: token")
    with pytest.raises(ValidationError):
        TaskResult(task_id="bad", domain="products", status="succeeded")
    with pytest.raises(ValidationError):
        TaskResult(task_id="bad", domain="products", status="failed", safe_error_code="task_execution_failed",
                   result={"should_not": "be present"})
    with pytest.raises(ValidationError, match="identity or credential"):
        TaskResult(task_id="bad", domain="products", status="succeeded",
                   result={"product_count": 3, "business_id": 123})
    with pytest.raises(ValidationError, match="identity or credential"):
        AgentFinding(finding_id="bad", domain="marketing", name="spend", value={"api_token": "private"},
                    source_service="marketing_intelligence", evidence_status="verified")
