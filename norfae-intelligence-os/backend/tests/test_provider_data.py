from copy import deepcopy
from datetime import date
import json

import pytest

from app.ai_engine.evidence_validation import ground_assistant_draft
from app.ai_engine.provider_data import (
    ProviderDataError, project_provider_evidence, sanitize_provider_facts,
)
from app.schemas.assistant_schema import AssistantClaim, AssistantDraft
from app.schemas.coordination_schema import (
    AgentFinding, ReportingPeriod, SharedFindingsContext, TaskResult,
)


def test_provider_facts_remove_internal_identifiers_recursively_without_mutating_source():
    original = {
        "profitability": {
            "business_id": 473,
            "start_date": "2026-09-01",
            "net_profit": {"amount": -12.5, "available": True, "source": "orders"},
            "orderId": 701,
            "nested": {"tenantID": 88, "ownerIdentifier": "private-owner"},
        },
        "data_quality": {
            "business_id": 473,
            "total_records_inspected": 3,
            "normalization_preview": [{"record_id": 701, "normalized_fields": {"sku": "PRIVATE"}}],
            "issues": [{"record_id": 701, "suggested_value": "PRIVATE"}],
            "generated_at": "2026-09-30T10:00:00Z",
        },
    }
    source_before = deepcopy(original)
    safe = sanitize_provider_facts(original)
    safe_json = json.dumps(safe)

    assert original == source_before
    assert "business_id" not in safe_json
    assert "473" not in safe_json
    assert "701" not in safe_json
    assert "tenantID" not in safe_json
    assert "ownerIdentifier" not in safe_json
    assert "normalization_preview" not in safe_json
    assert "PRIVATE" not in safe_json
    assert "generated_at" not in safe_json
    assert safe["profitability"]["net_profit"] == {
        "amount": -12.5, "available": True, "source": "orders",
    }
    assert safe["profitability"]["start_date"] == "2026-09-01"
    assert safe["data_quality"]["total_records_inspected"] == 3


def test_unknown_fact_roots_and_non_json_values_fail_closed():
    with pytest.raises(ProviderDataError):
        sanitize_provider_facts({"unreviewed_new_service_output": {"metric": 10}})
    with pytest.raises(ProviderDataError):
        sanitize_provider_facts({"profitability": {"metric": object()}})
    with pytest.raises(ProviderDataError):
        sanitize_provider_facts({"profitability": {"metric": float("nan")}})


def test_provider_evidence_uses_opaque_aliases_and_restores_internal_claim_references():
    finding = AgentFinding(
        finding_id="products:product_839_contribution", domain="products",
        name="product_839_contribution", value=-12.5,
        reporting_period=ReportingPeriod(start_date=date(2026, 9, 1), end_date=date(2026, 9, 30)),
        source_service="ProductIntelligenceService.analyze_business", evidence_ref="products",
        evidence_status="estimated", unit="currency_amount",
        metric_definition="recorded contribution after costs", limitations=["Cost data is incomplete."],
    )
    projection = project_provider_evidence([finding], [])
    encoded = json.dumps(projection.findings[0])
    assert "product_839" not in encoded
    assert '"finding_id": "finding_001"' in encoded
    assert '"metric_name": "metric_001"' in encoded
    assert "source_service" not in encoded
    assert "evidence_ref" not in encoded
    assert "currency_amount" in encoded
    assert "2026-09-01" in encoded
    assert "recorded contribution after costs" in encoded
    assert "Cost data is incomplete." in encoded

    provider_draft = AssistantDraft(
        answer="unused provider prose",
        claims=[AssistantClaim(
            claim_id="claim-1", text="ignored", finding_ids=["finding_001"],
            domain="products", metric_name="metric_001",
            period_start="2026-09-01", period_end="2026-09-30",
            claim_type="numeric", value=-12.5, unit="currency_amount",
        )],
    )
    restored = projection.restore_draft_references(provider_draft)
    assert restored.claims[0].finding_ids == [finding.finding_id]
    assert restored.claims[0].metric_name == finding.name


def test_evidence_validation_still_uses_original_findings_after_provider_projection():
    finding = AgentFinding(
        finding_id="profitability:net_profit", domain="profitability", name="net_profit",
        value=0, reporting_period=ReportingPeriod(start_date="2026-09-01", end_date="2026-09-30"),
        source_service="DeterministicProfitabilityService.overall", evidence_ref="profitability",
        evidence_status="verified", unit="currency_amount",
    )
    shared = SharedFindingsContext().with_finding(finding).with_task_result(TaskResult(
        task_id="profitability", domain="profitability", status="succeeded",
        result={"profitability": {"net_profit": 0}}, finding_ids=[finding.finding_id],
    ))
    provider_facts = sanitize_provider_facts({
        "profitability": {"business_id": 999, "net_profit": 0},
    })
    projection = project_provider_evidence([finding], [])
    provider_draft = AssistantDraft(
        answer="ignored", claims=[AssistantClaim(
            claim_id="claim-1", text="ignored", finding_ids=["finding_001"],
            domain="profitability", metric_name="metric_001",
            period_start="2026-09-01", period_end="2026-09-30",
            claim_type="numeric", value=0, unit="currency_amount",
        )],
    )
    restored = projection.restore_draft_references(provider_draft)
    final = ground_assistant_draft(restored, shared, [], set(provider_facts))
    assert final.answer.startswith("Calculated net profit: 0")
    assert final.answer_evidence_ids == ["profitability"]
