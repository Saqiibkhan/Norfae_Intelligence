from datetime import date

import pytest
from pydantic import ValidationError

from app.ai_engine.evidence_validation import ground_assistant_draft
from app.ai_engine.finding_extraction import extract_findings
from app.ai_engine.provider_data import project_provider_evidence
from app.schemas.assistant_schema import AssistantClaim, AssistantDraft
from app.schemas.coordination_schema import ProfitabilityComparison, SharedFindingsContext, TaskResult
from app.schemas.intelligence_schema import ProfitabilityComponent, ProfitabilitySummary
from app.ai_engine.task_adapters import ProfitabilityTaskOutput


SERVICE = "DeterministicProfitabilityService.overall"


def _summary(start, end, value, *, available=True):
    component = ProfitabilityComponent(amount=value, available=available)
    return ProfitabilitySummary(
        business_id=901, start_date=start, end_date=end,
        orders_inspected=4, delivered_orders=4, cancelled_orders=0,
        returned_orders=0, other_status_orders=0,
        gross_revenue=component, discounts=component, refunds=component,
        net_revenue=component, cost_of_goods_sold=component,
        packaging_cost=component, delivery_cost=component,
        advertising_expense=component, other_business_expenses=component,
        net_profit=component, profit_margin_percent=None, complete=True, warnings=[],
    )


def _findings(current=80, previous=50, *, current_dates=(date(2026, 9, 1), date(2026, 9, 30)),
              previous_dates=(date(2026, 8, 2), date(2026, 8, 31)),
              current_available=True, previous_available=True):
    output = ProfitabilityTaskOutput(
        profitability=_summary(*current_dates, current, available=current_available),
        previous_period_profitability=_summary(*previous_dates, previous, available=previous_available),
        product_profitability=[],
    )
    return extract_findings("profitability", "profitability", output)


def _shared(trend):
    return SharedFindingsContext().with_finding(trend).with_task_result(TaskResult(
        task_id="profitability", domain="profitability", status="succeeded",
        result={"profitability": {}, "previous_period_profitability": {}},
        finding_ids=[trend.finding_id],
    ))


def _claim(trend, *, value=None, start=None, end=None):
    comparison = trend.comparison
    return AssistantClaim(
        claim_id="claim-trend", text="ignored", finding_ids=[trend.finding_id],
        domain="profitability", metric_name="net_profit_trend",
        period_start=start or comparison.current_period_start,
        period_end=end or comparison.current_period_end,
        claim_type="qualitative",
        value=comparison.claim_value() if value is None else value,
        unit=comparison.unit,
    )


def test_current_and_previous_periods_and_changes_are_explicit_and_correct():
    trend = _findings(80, 50)[2]
    assert trend.comparison.current_period_start == date(2026, 9, 1)
    assert trend.comparison.current_period_end == date(2026, 9, 30)
    assert trend.comparison.previous_period_start == date(2026, 8, 2)
    assert trend.comparison.previous_period_end == date(2026, 8, 31)
    assert trend.comparison.absolute_change == 30
    assert trend.comparison.percentage_change == 60


def test_negative_profit_values_use_signed_change_and_absolute_prior_denominator():
    trend = _findings(-20, -50)[2]
    assert trend.comparison.direction == "increase"
    assert trend.comparison.absolute_change == 30
    assert trend.comparison.percentage_change == 60
    decline = _findings(-80, -50)[2]
    assert decline.comparison.direction == "decrease"
    assert decline.comparison.absolute_change == -30
    assert decline.comparison.percentage_change == -60


def test_zero_previous_value_has_no_percentage_change():
    trend = _findings(25, 0)[2]
    assert trend.comparison.absolute_change == 25
    assert trend.comparison.percentage_change is None


def test_missing_previous_value_is_unavailable_and_not_a_complete_trend():
    trend = _findings(25, None, previous_available=False)[2]
    assert trend.value is None
    assert trend.comparison.status == "unavailable"
    assert trend.comparison.unavailable_reason == "previous_value_unavailable"
    final = ground_assistant_draft(AssistantDraft(answer="ignored"), _shared(trend), [], {"profitability"})
    assert "comparison cannot be calculated" in final.answer
    assert "previous period 2026-08-02 to 2026-08-31" in final.answer


def test_invalid_or_reversed_date_ranges_are_rejected():
    with pytest.raises(ValidationError):
        _findings(current_dates=(date(2026, 9, 30), date(2026, 9, 1)))
    with pytest.raises(ValidationError):
        ProfitabilityComparison(
            current_period_start=date(2026, 9, 30), current_period_end=date(2026, 9, 1),
            previous_period_start=date(2026, 8, 2), previous_period_end=date(2026, 8, 31),
            current_value=80, previous_value=50, absolute_change=30,
            percentage_change=60, direction="increase", unit="currency_amount",
            comparison_definition="same definition", status="comparable",
            current_evidence_ref="profitability", previous_evidence_ref="previous_period_profitability",
        )


@pytest.mark.parametrize("previous_dates, reason", [
    ((date(2026, 8, 1), date(2026, 8, 31)), "periods_incompatible"),
    ((date(2026, 8, 2), date(2026, 8, 30)), "periods_incompatible"),
])
def test_non_adjacent_or_different_length_intervals_are_not_comparable(previous_dates, reason):
    trend = _findings(previous_dates=previous_dates)[2]
    assert trend.comparison.status == "incompatible"
    assert trend.comparison.unavailable_reason == reason
    assert trend.value is None


def test_incompatible_units_are_not_compared():
    from app.ai_engine.finding_extraction import _profitability_comparison

    current, previous, _ = _findings()
    previous = previous.model_copy(update={"unit": "percent"})
    comparison = _profitability_comparison(current, previous)
    assert comparison.status == "incompatible"
    assert comparison.unavailable_reason == "unit_mismatch"

    previous = previous.model_copy(update={"unit": "currency_amount", "source_service": "OtherProfitabilityService.overall"})
    comparison = _profitability_comparison(current, previous)
    assert comparison.status == "incompatible"
    assert comparison.unavailable_reason == "source_mismatch"


@pytest.mark.parametrize("tamper", ["previous_dates", "percentage"])
def test_claim_cannot_change_previous_period_or_percentage(tamper):
    trend = _findings()[2]
    value = trend.comparison.claim_value()
    if tamper == "previous_dates":
        value["previous_period_start"] = "2026-08-01"
        value["previous_period_end"] = "2026-08-30"
    else:
        value["percentage_change"] = 99
    draft = AssistantDraft(answer="ignored", claims=[_claim(trend, value=value)])
    final = ground_assistant_draft(draft, _shared(trend), [], {"profitability"})
    assert "could not validate" in final.answer


def test_deterministic_trend_rendering_shows_ranges_values_changes_and_no_cause():
    trend = _findings(80, 50)[2]
    final = ground_assistant_draft(
        AssistantDraft(answer="profit rose because of a promotion", claims=[_claim(trend)]),
        _shared(trend), [], {"profitability"},
    )
    assert "increased from 50.00 currency_amount in 2026-08-02 to 2026-08-31" in final.answer
    assert "to 80.00 currency_amount in 2026-09-01 to 2026-09-30" in final.answer
    assert "Absolute change: +30.00 currency_amount" in final.answer
    assert "Percentage change: +60.00%" in final.answer
    assert "does not establish a cause" in final.answer
    assert "promotion" not in final.answer


def test_provider_alias_projection_keeps_new_fields_but_not_internal_evidence_keys():
    trend = _findings()[2]
    projection = project_provider_evidence([trend], [])
    projected = projection.findings[0]
    comparison = projected["comparison"]
    assert comparison["current_period_start"] == "2026-09-01"
    assert comparison["previous_period_end"] == "2026-08-31"
    assert comparison["percentage_change"] == 60
    assert "current_evidence_ref" not in comparison
    assert "previous_evidence_ref" not in comparison
    assert projected["finding_id"] == "finding_001"
    assert projected["metric_name"] == "metric_001"

    provider_draft = AssistantDraft(answer="ignored", claims=[AssistantClaim(
        claim_id="claim-trend", text="ignored", finding_ids=["finding_001"],
        domain="profitability", metric_name="metric_001",
        period_start="2026-09-01", period_end="2026-09-30",
        claim_type="qualitative", value=projected["value"], unit="currency_amount",
    )])
    restored = projection.restore_draft_references(provider_draft)
    final = ground_assistant_draft(restored, _shared(trend), [], {"profitability"})
    assert "Percentage change: +60.00%" in final.answer


def test_comparison_schema_rejects_wrong_delta_or_percentage():
    trend = _findings()[2]
    payload = trend.comparison.model_dump()
    payload["percentage_change"] = 12
    with pytest.raises(ValidationError):
        ProfitabilityComparison(**payload)

