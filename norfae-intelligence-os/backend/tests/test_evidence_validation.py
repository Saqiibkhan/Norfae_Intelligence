from datetime import date

import pytest
from pydantic import ValidationError

from app.ai_engine.evidence_validation import (
    detect_evidence_conflicts, enforce_conflict_policy, ground_assistant_draft,
    validate_shared_evidence,
)
from app.schemas.assistant_schema import (
    AssistantClaim, AssistantDraft, AssistantRecommendationIntent,
)
from app.schemas.coordination_schema import (
    AgentFinding, ReportingPeriod, SharedFindingsContext, TaskResult,
)


PERIOD = ReportingPeriod(start_date=date(2026, 9, 1), end_date=date(2026, 9, 30))


def _finding(task, value, *, name="revenue", period=PERIOD, definition="delivered revenue",
             evidence_ref="profitability", status="verified", classification=None,
             unit="currency_amount"):
    return AgentFinding(
        finding_id=f"{task}:{name}", domain="profitability", name=name, value=value,
        reporting_period=period, source_service="DeterministicProfitabilityService.overall",
        evidence_ref=evidence_ref, evidence_status=status, evidence_classification=classification,
        metric_definition=definition, unit=unit,
    )


def _shared(finding, *, result_key="profitability", task="profitability"):
    result = TaskResult(
        task_id=task, domain="profitability", status="succeeded",
        result={result_key: {"value": finding.value}}, finding_ids=[finding.finding_id],
    )
    return SharedFindingsContext().with_task_result(result).with_finding(finding)


def _claim(finding, *, claim_id="claim-1", value=None, metric=None, period=PERIOD,
           domain="profitability", unit="currency_amount", claim_type="numeric", text=None,
           finding_ids=None):
    return AssistantClaim(
        claim_id=claim_id, text=text or "The profit rose by 999 percent.",
        finding_ids=finding_ids or [finding.finding_id], domain=domain,
        metric_name=metric or finding.name,
        period_start=period.start_date if period else None,
        period_end=period.end_date if period else None,
        claim_type=claim_type, value=finding.value if value is None else value, unit=unit,
    )


def _draft(*, claims=(), intents=(), answer="Untrusted text claims profit rose by 999%.", recommendations=()):
    return AssistantDraft(
        answer=answer, answer_evidence_ids=["profitability"],
        recommendations=list(recommendations), claims=list(claims),
        recommendation_intents=list(intents),
    )


def test_evidence_classifications_preserve_zero_and_unavailable_values():
    observed = _finding("a", 0, classification="OBSERVED")
    calculated = _finding("b", 12, classification="CALCULATED")
    inferred = _finding("c", "possible explanation", classification="INFERRED")
    unavailable = _finding("d", None, status="unavailable")
    assert observed.value == 0 and observed.data_availability == "available"
    assert calculated.evidence_classification == "CALCULATED"
    assert inferred.evidence_classification == "INFERRED"
    assert unavailable.evidence_classification == "UNAVAILABLE"
    assert unavailable.data_availability == "unavailable"
    with pytest.raises(ValidationError):
        _finding("bad", 0, status="unavailable")


def test_validation_requires_successful_task_result_and_real_evidence_reference():
    valid = _finding("profitability", 25)
    report = validate_shared_evidence(_shared(valid))
    assert report.findings == [valid]
    forged = _finding("profitability", 25, evidence_ref="llm_invented_reference")
    report = validate_shared_evidence(_shared(forged))
    assert report.findings == []
    assert report.invalid_finding_ids == [forged.finding_id]
    assert report.safe_errors == ["evidence_reference_missing"]


def test_conflict_detector_only_compares_compatible_same_metric_evidence():
    left = _finding("source_a", 100)
    right = _finding("source_b", 120, evidence_ref="products")
    conflict, = detect_evidence_conflicts([left, right])
    assert (conflict.category, conflict.outcome) == ("VALUE_MISMATCH", "UNRESOLVED")

    later_period = _finding(
        "source_c", 120, period=ReportingPeriod(start_date="2026-08-01", end_date="2026-08-31"),
    )
    conflict, = detect_evidence_conflicts([left, later_period])
    assert (conflict.category, conflict.outcome) == ("PERIOD_MISMATCH", "NOT_COMPARABLE")

    different_definition = _finding("source_d", 120, definition="all-order revenue")
    conflict, = detect_evidence_conflicts([left, different_definition])
    assert (conflict.category, conflict.outcome) == ("DEFINITION_MISMATCH", "NOT_COMPARABLE")

    missing = _finding("source_e", None, status="unavailable")
    conflict, = detect_evidence_conflicts([left, missing])
    assert (conflict.category, conflict.outcome) == ("SOURCE_UNAVAILABLE", "INSUFFICIENT_DATA")

    roas = _finding("source_f", 2.0, name="roas", definition="conversion value / spend", evidence_ref="marketing")
    assert detect_evidence_conflicts([left, roas]) == []


def test_unresolved_conflict_overrides_contradictory_llm_narrative():
    left = _finding("profitability", 100)
    right = _finding("marketing", 120, evidence_ref="marketing_overview")
    conflict, = detect_evidence_conflicts([left, right])
    draft = AssistantDraft(
        answer="The revenue is definitely 100 and there is no discrepancy.",
        answer_evidence_ids=["profitability"],
    )
    safe = enforce_conflict_policy(
        draft, [conflict], [left, right], {"profitability", "marketing_overview"},
    )
    assert "unresolved" in safe.answer
    assert "neither source is treated as authoritative" in safe.answer
    assert safe.answer != draft.answer
    assert safe.answer_evidence_ids == ["marketing_overview", "profitability"]


def test_request_context_does_not_validate_findings_from_another_request():
    source = _finding("profitability", 10)
    request_a = _shared(source)
    request_b = SharedFindingsContext()
    assert validate_shared_evidence(request_a).findings == [source]
    assert validate_shared_evidence(request_b).findings == []


def test_structured_claim_requires_existing_provenance_and_relevant_metric_period():
    finding = _finding("profitability", 15)
    shared = _shared(finding)
    facts = {"profitability"}
    valid = ground_assistant_draft(_draft(claims=[_claim(finding)]), shared, [], facts)
    assert valid.answer == "Calculated revenue: 15 currency_amount for 2026-09-01 to 2026-09-30."
    assert valid.answer_evidence_ids == ["profitability"]
    assert "999" not in valid.answer

    nonexistent = _draft(claims=[_claim(finding, finding_ids=["other:revenue"])])
    assert "could not validate" in ground_assistant_draft(nonexistent, shared, [], facts).answer

    wrong_metric = _draft(claims=[_claim(finding, metric="net_profit")])
    assert "could not validate" in ground_assistant_draft(wrong_metric, shared, [], facts).answer

    wrong_period = _draft(claims=[_claim(
        finding, period=ReportingPeriod(start_date="2026-08-01", end_date="2026-08-31"),
    )])
    assert "could not validate" in ground_assistant_draft(wrong_period, shared, [], facts).answer


def test_failed_task_findings_cannot_support_claims():
    finding = _finding("profitability", 15)
    failed = TaskResult(
        task_id="profitability", domain="profitability", status="failed",
        safe_error_code="task_execution_failed", finding_ids=[finding.finding_id],
    )
    shared = SharedFindingsContext().with_task_result(failed).with_finding(finding)
    grounded = ground_assistant_draft(_draft(claims=[_claim(finding)]), shared, [], {"profitability"})
    assert "could not validate" in grounded.answer
    assert grounded.answer_evidence_ids == []


def test_numeric_and_percentage_claims_require_exact_structured_value_and_unit():
    finding = _finding("profitability", 15, name="revenue")
    wrong_unit = _claim(finding, value=15, unit="percent")
    grounded = ground_assistant_draft(_draft(claims=[wrong_unit]), _shared(finding), [], {"profitability"})
    assert "could not validate" in grounded.answer

    percentage = _finding("profitability", 15, name="margin", unit="percent")
    wrong_calculation = _claim(percentage, value=20, unit="percent")
    grounded = ground_assistant_draft(
        _draft(claims=[wrong_calculation]), _shared(percentage), [], {"profitability"},
    )
    assert "could not validate" in grounded.answer
    correct = _claim(percentage, value=15, unit="percent")
    grounded = ground_assistant_draft(_draft(claims=[correct]), _shared(percentage), [], {"profitability"})
    assert "margin: 15 percent" in grounded.answer


def test_unavailable_value_cannot_be_claimed_as_zero_and_estimates_are_labeled():
    unavailable = _finding("profitability", None, status="unavailable")
    unavailable_claim = _claim(unavailable, value=0)
    grounded = ground_assistant_draft(
        _draft(claims=[unavailable_claim]), _shared(unavailable), [], {"profitability"},
    )
    assert "could not validate" in grounded.answer
    assert "0" not in grounded.answer

    estimate = _finding("profitability", 15, status="estimated")
    grounded = ground_assistant_draft(
        _draft(claims=[_claim(estimate)]), _shared(estimate), [], {"profitability"},
    )
    assert grounded.answer.startswith("Estimated revenue: 15")


def test_conflicted_finding_cannot_be_presented_as_established_claim():
    left = _finding("source_a", 100)
    right = _finding("source_b", 120, evidence_ref="products")
    findings = [left, right]
    shared = SharedFindingsContext()
    for finding, result_key in ((left, "profitability"), (right, "products")):
        shared = shared.with_task_result(TaskResult(
            task_id=finding.finding_id.split(":")[0], domain="profitability",
            status="succeeded", result={result_key: {"value": finding.value}},
            finding_ids=[finding.finding_id],
        )).with_finding(finding)
    conflict, = detect_evidence_conflicts(findings)
    grounded = ground_assistant_draft(
        _draft(claims=[_claim(left)]), shared, [conflict], {"profitability", "products"},
    )
    assert "could not validate" in grounded.answer


def test_multiple_findings_and_multiple_claims_are_individually_validated():
    left = _finding("source_a", 100)
    right = _finding("source_b", 100, evidence_ref="products")
    shared = SharedFindingsContext()
    for finding, fact in ((left, "profitability"), (right, "products")):
        shared = shared.with_task_result(TaskResult(
            task_id=finding.finding_id.split(":")[0], domain="profitability", status="succeeded",
            result={fact: {"value": finding.value}}, finding_ids=[finding.finding_id],
        )).with_finding(finding)
    both = _claim(left, finding_ids=[left.finding_id, right.finding_id])
    second = _claim(right, claim_id="claim-2", value=100, text="Second claim")
    grounded = ground_assistant_draft(
        _draft(claims=[both, second]), shared, [], {"profitability", "products"},
    )
    assert grounded.answer.count("revenue: 100") == 2
    assert grounded.answer_evidence_ids == ["profitability", "products"]


def test_recommendation_intents_are_allowlisted_and_evidence_grounded():
    finding = _finding("profitability", 15)
    valid_intent = AssistantRecommendationIntent(
        action="review_metric", finding_ids=[finding.finding_id],
    )
    unsupported = AssistantDraft(
        answer="Untrusted", recommendations=[
            {"text": "Double advertising immediately", "evidence_ids": ["profitability"]},
        ],
    )
    grounded = ground_assistant_draft(
        unsupported.model_copy(update={"recommendation_intents": [valid_intent]}),
        _shared(finding), [], {"profitability"},
    )
    assert len(grounded.recommendations) == 1
    assert grounded.recommendations[0].evidence_ids == ["profitability"]
    assert "Review the recorded evidence for revenue" in grounded.recommendations[0].text
    assert all("Double advertising" not in item.text for item in grounded.recommendations)

    invalid_ref = AssistantRecommendationIntent(action="review_metric", finding_ids=["foreign:revenue"])
    grounded = ground_assistant_draft(
        _draft(intents=[invalid_ref]), _shared(finding), [], {"profitability"},
    )
    assert grounded.recommendations == []


def test_empty_malformed_oversized_and_cross_request_claims_fail_safely():
    finding = _finding("profitability", 15)
    empty = ground_assistant_draft(_draft(), _shared(finding), [], {"profitability"})
    assert "could not validate" in empty.answer
    with pytest.raises(ValidationError):
        _claim(finding, finding_ids=[finding.finding_id] * 6)
    with pytest.raises(ValidationError):
        AssistantClaim(
            claim_id="c", text="x" * 501, finding_ids=[finding.finding_id],
            domain="profitability", metric_name="revenue",
            period_start=PERIOD.start_date, period_end=PERIOD.end_date,
            claim_type="numeric", value=15, unit="currency_amount",
        )
    with pytest.raises(ValidationError):
        _claim(finding, period=ReportingPeriod(
            start_date="2026-10-01", end_date="2026-09-01",
        ))
    with pytest.raises(ValidationError):
        AssistantDraft(answer="bad", claims=[_claim(finding)] * 13)
    cross_business = ground_assistant_draft(
        _draft(claims=[_claim(finding)]), SharedFindingsContext(), [], {"profitability"},
    )
    assert "could not validate" in cross_business.answer
