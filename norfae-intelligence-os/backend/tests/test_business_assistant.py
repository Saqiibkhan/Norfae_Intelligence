import json

import pytest

from app.llm.errors import OpenRouterTimeoutError
from app.ai_engine.execution_budget import RequestBudgetExceeded
from app.ai_engine.task_adapters import (
    DataQualityTaskOutput, MarketingTaskAdapter, TaskAdapterError, TaskAdapterRegistry,
)
from app.schemas.assistant_schema import AssistantClaim, AssistantDraft, AssistantIntent
from app.schemas.intelligence_schema import DataQualityReport
from app.schemas.intelligence_schema import DataQualityIssue, DataQualityReport, NormalizationPreview
from app.services.data_quality_service import DataQualityService
from app.routers import assistant as assistant_router_module


INTENTS = {
    "profit": "profitability", "product": "products", "city": "cities",
    "marketing": "marketing", "creative": "creatives", "anomaly": "anomalies",
    "overview": "overview", "recommend": "recommendations", "quality": "data_quality",
    "multi": "multi_domain",
}


class FakeOpenRouter:
    def __init__(self, *, failure=None, malformed=None):
        self.failure = failure
        self.malformed = malformed
        self.calls = 0

    async def chat_completion(self, messages, **_kwargs):
        self.calls += 1
        if self.failure:
            raise self.failure
        if self.malformed is not None:
            return self.malformed
        if "Classify the user's current" in messages[0]["content"]:
            question = messages[-1]["content"].casefold()
            intent = next((value for key, value in INTENTS.items() if key in question), "unsupported")
            domains = ["products", "cities", "marketing"] if intent == "multi_domain" else []
            return json.dumps({"intent": intent, "start_date": "2026-09-01", "end_date": "2026-09-30",
                               "requested_domains": domains})
        facts_text = messages[-1]["content"].split("verified_facts: ", 1)[1].split("\ntool_status:", 1)[0]
        facts = json.loads(facts_text)
        return json.dumps({
            "answer": "No recorded delivered revenue for this period.",
            "answer_evidence_ids": list(facts)[:8],
            "interpretation": "The selected data contains no delivered revenue.",
            "recommendations": [],
            "unknowns": ["Discounts and refunds are not represented."],
        })


def _register(client, email):
    return client.post("/auth/register", json={
        "email": email, "password": "correct-horse-battery-staple", "business_name": email.split("@")[0],
    })


def _headers(auth):
    return {"Authorization": f"Bearer {auth.json()['access_token']}",
            "X-Business-ID": str(auth.json()["business"]["id"])}


@pytest.mark.parametrize("word,intent", INTENTS.items())
def test_assistant_supported_intents_use_mocked_llm_and_existing_services(api_client, monkeypatch, word, intent):
    monkeypatch.setattr(assistant_router_module, "assistant_service",
                        assistant_router_module.BusinessAssistantService(FakeOpenRouter()))
    auth = _register(api_client, f"assistant-{word}@example.com")
    response = api_client.post("/assistant/chat", headers=_headers(auth), json={"message": f"Tell me about {word}"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["intent"] == intent
    assert "conversation_id" in result
    assert isinstance(result["verified_facts"], dict)
    assert result["execution"]["status"] == "complete"
    if intent == "multi_domain":
        assert result["execution"]["tools"]["products"] == "success"
        assert result["execution"]["tools"]["cities"] == "success"
        assert result["execution"]["tools"]["marketing"] == "success"
        assert result["execution"]["tools"]["creatives"] == "skipped"


def test_coordination_contracts_preserve_assistant_response_contract(api_client, monkeypatch):
    monkeypatch.setattr(assistant_router_module, "assistant_service",
                        assistant_router_module.BusinessAssistantService(FakeOpenRouter()))
    auth = _register(api_client, "assistant-contract@example.com")
    response = api_client.post("/assistant/chat", headers=_headers(auth), json={"message": "Tell me about profit"})
    assert response.status_code == 200
    assert set(response.json()) == {
        "conversation_id", "intent", "answer", "answer_evidence_ids", "verified_facts",
        "interpretation", "recommendations", "unknowns", "limitations", "execution",
    }


def test_assistant_graph_renders_only_validated_structured_claims(api_client, monkeypatch):
    class StructuredClaimRouter(FakeOpenRouter):
        async def chat_completion(self, messages, **kwargs):
            if "Classify the user's current" in messages[0]["content"]:
                return json.dumps({"intent": "data_quality", "requested_domains": []})
            evidence_text = messages[-1]["content"].split("\nvalidated_evidence: ", 1)[1].split(
                "\nevidence_conflicts:", 1
            )[0]
            findings = json.loads(evidence_text)
            finding = next(item for item in findings if item["metric_label"] == "total records inspected")
            # Both free text strings deliberately contradict the service value and
            # are ignored by the deterministic response renderer.
            return json.dumps({
                "answer": "Revenue increased by 999 percent.",
                "answer_evidence_ids": ["data_quality"],
                "interpretation": "The business is definitely growing.",
                "recommendations": [{"text": "Double ad spend now", "evidence_ids": ["data_quality"]}],
                "unknowns": [],
                "claims": [{
                    "claim_id": "claim-record-count", "text": "Revenue increased by 999 percent.",
                    "finding_ids": [finding["finding_id"]], "domain": finding["domain"],
                    "metric_name": finding["metric_name"],
                    "period_start": (finding["reporting_period"] or {}).get("start_date"),
                    "period_end": (finding["reporting_period"] or {}).get("end_date"),
                    "claim_type": "numeric", "value": finding["value"], "unit": finding["unit"],
                }],
                "recommendation_intents": [{
                    "action": "review_metric", "finding_ids": [finding["finding_id"]],
                }],
            })

    monkeypatch.setattr(assistant_router_module, "assistant_service",
                        assistant_router_module.BusinessAssistantService(StructuredClaimRouter()))
    auth = _register(api_client, "assistant-grounded-claims@example.com")
    response = api_client.post("/assistant/chat", headers=_headers(auth), json={"message": "quality"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert "Calculated total records inspected: 0 count" in result["answer"]
    assert "999" not in result["answer"]
    assert "growing" not in result["interpretation"]
    assert "Double ad spend" not in str(result["recommendations"])
    assert result["answer_evidence_ids"] == ["data_quality"]
    assert result["recommendations"][0]["evidence_ids"] == ["data_quality"]


def test_provider_requests_exclude_internal_ids_but_retain_internal_results(api_client, monkeypatch):
    calls = []

    class CapturingRouter:
        async def chat_completion(self, messages, **_kwargs):
            calls.append(messages)
            if "Classify the user's current" in messages[0]["content"]:
                return json.dumps({"intent": "data_quality", "requested_domains": []})
            prompt_text = messages[-1]["content"]
            facts_text = prompt_text.split("verified_facts: ", 1)[1].split("\ntool_status:", 1)[0]
            facts = json.loads(facts_text)
            evidence_text = prompt_text.split("\nvalidated_evidence: ", 1)[1].split(
                "\nevidence_conflicts:", 1
            )[0]
            findings = json.loads(evidence_text)
            finding = next(item for item in findings if item["metric_label"] == "total records inspected")
            assert facts["data_quality"]["total_records_inspected"] == 3
            return json.dumps({
                "answer": "Ignored provider prose with ID 473.",
                "claims": [{
                    "claim_id": "count", "text": "ignored", "finding_ids": [finding["finding_id"]],
                    "domain": finding["domain"], "metric_name": finding["metric_name"],
                    "period_start": None, "period_end": None,
                    "claim_type": "numeric", "value": finding["value"], "unit": finding["unit"],
                }],
                "recommendation_intents": [],
            })

    def analyze_with_internal_metadata(_db, business_id):
        return DataQualityReport(
            business_id=business_id, generated_at="2026-09-30T10:00:00Z",
            total_records_inspected=3, valid_records=2, invalid_records=1,
            missing_fields={"sku": 1}, duplicate_records={"order_id": 1},
            warnings=["One record contains an incomplete SKU."],
            recommended_corrections=["Complete the missing SKU at its source."],
            normalization_preview=[NormalizationPreview(
                record_type="order", record_id=821,
                normalized_fields={"order_id": "INTERNAL-ORDER-821"},
            )],
            issues=[DataQualityIssue(
                record_type="order", record_id=933, code="missing_sku", field="sku",
                message="SKU is missing.", suggested_value="SECRET-SKU-VALUE",
            )],
        )

    monkeypatch.setattr(DataQualityService, "analyze", analyze_with_internal_metadata)
    monkeypatch.setattr(assistant_router_module, "assistant_service",
                        assistant_router_module.BusinessAssistantService(CapturingRouter()))
    auth = _register(api_client, "assistant-provider-minimization@example.com")
    business_id = auth.json()["business"]["id"]
    response = api_client.post("/assistant/chat", headers=_headers(auth), json={"message": "quality"})
    assert response.status_code == 200, response.text
    assert len(calls) == 2

    # Classification gets the current question and user-authored history only,
    # never the service facts or prior assistant result content.
    classification_payload = json.dumps(calls[0])
    assert "verified_facts" not in classification_payload
    assert "business_id" not in classification_payload
    assert "INTERNAL-ORDER-821" not in classification_payload

    draft_payload = json.dumps(calls[1])
    draft_user_content = calls[1][-1]["content"]
    provider_facts = json.loads(
        draft_user_content.split("verified_facts: ", 1)[1].split("\ntool_status:", 1)[0]
    )
    assert "business_id" not in provider_facts["data_quality"]
    for sensitive in (
        "business_id", "record_id", "821", "933",
        "normalization_preview", "issues", "suggested_value", "SECRET-SKU-VALUE",
    ):
        assert sensitive not in draft_payload
    assert "total_records_inspected" in draft_payload
    assert "missing_fields" in draft_payload
    assert "incomplete SKU" in draft_payload
    assert "count" in draft_payload
    assert "unit" in draft_payload
    assert "metric_definition" in draft_payload

    # Provider projection is separate: the existing API result remains intact.
    result = response.json()
    raw = result["verified_facts"]["data_quality"]
    assert raw["business_id"] == business_id
    assert raw["normalization_preview"][0]["record_id"] == 821
    assert raw["issues"][0]["record_id"] == 933
    assert raw["issues"][0]["suggested_value"] == "SECRET-SKU-VALUE"
    assert result["answer"].startswith("Calculated total records inspected: 3")


@pytest.mark.anyio
async def test_classifier_omits_prior_assistant_business_result_text():
    captured = []

    class CaptureClassifier:
        async def chat_completion(self, messages, **_kwargs):
            captured.extend(messages)
            return json.dumps({"intent": "products", "requested_domains": []})

    service = assistant_router_module.BusinessAssistantService(CaptureClassifier())
    await service._classify("What about those products?", [
        {"role": "user", "content": "Show me the product summary."},
        {"role": "assistant", "content": "business_id=473; record_id=821; revenue=400."},
    ])
    payload = json.dumps(captured)
    assert "Show me the product summary." in payload
    assert "business_id=473" not in payload
    assert "record_id=821" not in payload
    assert "revenue=400" not in payload


def test_unsupported_question_skips_all_analysis_tools(api_client, monkeypatch):
    llm = FakeOpenRouter()
    monkeypatch.setattr(assistant_router_module, "assistant_service",
                        assistant_router_module.BusinessAssistantService(llm))
    auth = _register(api_client, "assistant-unsupported@example.com")
    response = api_client.post("/assistant/chat", headers=_headers(auth), json={"message": "What is the weather?"})
    assert response.status_code == 200
    assert response.json()["intent"] == "unsupported"
    assert response.json()["execution"]["status"] == "unsupported"
    assert all(value == "skipped" for value in response.json()["execution"]["tools"].values())
    assert llm.calls == 1


def test_multi_domain_request_returns_partial_success_and_safe_tool_status(api_client, monkeypatch):
    async def fail_marketing(self, task, context):
        raise TaskAdapterError("INTERNAL_ERROR")

    monkeypatch.setattr(MarketingTaskAdapter, "execute", fail_marketing)
    monkeypatch.setattr(assistant_router_module, "assistant_service",
                        assistant_router_module.BusinessAssistantService(FakeOpenRouter()))
    auth = _register(api_client, "assistant-partial@example.com")
    response = api_client.post("/assistant/chat", headers=_headers(auth), json={"message": "multi domain analysis"})
    assert response.status_code == 200
    result = response.json()
    assert result["execution"]["status"] == "partial"
    assert result["execution"]["tools"]["marketing"] == "failed"
    assert "database details" not in response.text
    assert result["execution"]["errors"] == ["marketing_tool_failed"]


def test_assistant_retries_only_classified_transient_task_failures(api_client, monkeypatch):
    calls = {"count": 0}
    original_execute = MarketingTaskAdapter.execute

    async def transient_once(self, task, context, execution_context=None, *, timeout_seconds=None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise TaskAdapterError("TRANSIENT_FAILURE")
        return await original_execute(
            self, task, context, execution_context, timeout_seconds=timeout_seconds,
        )

    monkeypatch.setattr(MarketingTaskAdapter, "execute", transient_once)
    monkeypatch.setattr(assistant_router_module, "assistant_service",
                        assistant_router_module.BusinessAssistantService(FakeOpenRouter()))
    auth = _register(api_client, "assistant-transient@example.com")
    response = api_client.post("/assistant/chat", headers=_headers(auth), json={"message": "Tell me about marketing"})
    assert response.status_code == 200, response.text
    assert calls["count"] == 2
    assert response.json()["execution"]["tools"]["marketing"] == "success"


def test_assistant_conversation_context_and_cross_business_access(api_client, monkeypatch):
    monkeypatch.setattr(assistant_router_module, "assistant_service",
                        assistant_router_module.BusinessAssistantService(FakeOpenRouter()))
    owner = _register(api_client, "assistant-owner@example.com")
    other = _register(api_client, "assistant-other@example.com")
    created = api_client.post("/assistant/chat", headers=_headers(owner), json={"message": "overview"})
    conversation_id = created.json()["conversation_id"]
    follow_up = api_client.post("/assistant/chat", headers=_headers(owner), json={
        "message": "What about the products?", "conversation_id": conversation_id,
    })
    foreign_get = api_client.get(f"/assistant/conversations/{conversation_id}", headers=_headers(other))
    foreign_delete = api_client.delete(f"/assistant/conversations/{conversation_id}", headers=_headers(other))
    own_detail = api_client.get(f"/assistant/conversations/{conversation_id}", headers=_headers(owner))
    own_delete = api_client.delete(f"/assistant/conversations/{conversation_id}", headers=_headers(owner))
    deleted_detail = api_client.get(f"/assistant/conversations/{conversation_id}", headers=_headers(owner))
    assert follow_up.status_code == 200
    assert own_detail.status_code == 200
    assert [m["role"] for m in own_detail.json()["messages"]] == ["user", "assistant", "user", "assistant"]
    assert foreign_get.status_code == foreign_delete.status_code == 404
    assert own_delete.status_code == 200
    assert deleted_detail.status_code == 404


def test_assistant_auth_invalid_context_and_provider_failures(api_client, monkeypatch):
    auth = _register(api_client, "assistant-errors@example.com")
    unauth = api_client.post("/assistant/chat", json={"message": "overview"})
    bad_business_headers = {"Authorization": _headers(auth)["Authorization"], "X-Business-ID": "99999"}
    unauthorized = api_client.post("/assistant/chat", headers=bad_business_headers, json={"message": "overview"})
    assert unauth.status_code == 401
    assert unauthorized.status_code == 404

    for fake in (
        FakeOpenRouter(failure=OpenRouterTimeoutError("private provider detail")),
        FakeOpenRouter(malformed="not json"),
        FakeOpenRouter(malformed=""),
        FakeOpenRouter(malformed=json.dumps({"intent": "overview", "business_id": 999})),
    ):
        monkeypatch.setattr(assistant_router_module, "assistant_service",
                            assistant_router_module.BusinessAssistantService(fake))
        response = api_client.post("/assistant/chat", headers=_headers(auth), json={"message": "overview"})
        assert response.status_code == 503
        assert "private provider detail" not in response.text


def test_no_usable_facts_preserves_system_generated_unavailable_explanation(api_client, monkeypatch):
    service = assistant_router_module.BusinessAssistantService(FakeOpenRouter())

    async def fail_task(*_args, **_kwargs):
        raise TaskAdapterError("DATA_UNAVAILABLE")

    monkeypatch.setattr(service.adapter_registry, "execute", fail_task)
    monkeypatch.setattr(assistant_router_module, "assistant_service", service)
    auth = _register(api_client, "assistant-no-facts@example.com")
    response = api_client.post("/assistant/chat", headers=_headers(auth), json={"message": "overview"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["answer"] == (
        "I could not retrieve verified results for this request. "
        "Check the execution status and try again later."
    )
    assert "No verified result was available" in result["unknowns"][0]
    assert "0" not in result["answer"]
    assert result["execution"]["status"] == "failed"


def test_llm_budget_exhaustion_preserves_system_fallback_and_evidence_ids(api_client, monkeypatch):
    service = assistant_router_module.BusinessAssistantService(FakeOpenRouter())

    async def exhaust_budget(*_args, **_kwargs):
        raise RequestBudgetExceeded()

    monkeypatch.setattr(service, "_draft", exhaust_budget)
    monkeypatch.setattr(assistant_router_module, "assistant_service", service)
    auth = _register(api_client, "assistant-budget-fallback@example.com")
    response = api_client.post("/assistant/chat", headers=_headers(auth), json={"message": "quality"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert "response-generation budget was reached" in result["answer"]
    assert result["answer_evidence_ids"] == ["data_quality"]
    assert "narrative response could not be generated" in result["unknowns"][0]
    assert result["execution"]["status"] == "complete"


def test_partial_failure_keeps_successful_claims_under_evidence_validation(api_client, monkeypatch):
    service = assistant_router_module.BusinessAssistantService(FakeOpenRouter())

    async def classify(*_args, **_kwargs):
        return AssistantIntent(intent="multi_domain", requested_domains=["data_quality", "marketing"])

    monkeypatch.setattr(service, "_classify", classify)

    async def run_selected_task(task, *_args, **_kwargs):
        if task.domain == "marketing":
            raise TaskAdapterError("INTERNAL_ERROR")
        return DataQualityTaskOutput(data_quality=DataQualityReport(
            business_id=1, generated_at="2026-11-18T00:00:00Z",
            total_records_inspected=4, valid_records=4, invalid_records=0,
            missing_fields={}, duplicate_records={}, warnings=[],
            recommended_corrections=[], normalization_preview=[], issues=[],
        ))

    async def grounded_draft(_question, _history, _facts, _tools, _errors, _budget, findings, _conflicts):
        finding = next(item for item in findings if item.name == "total_records_inspected")
        return AssistantDraft(answer="untrusted", claims=[AssistantClaim(
            claim_id="count", text="ignored", finding_ids=[finding.finding_id],
            domain="data_quality", metric_name=finding.name,
            period_start=None, period_end=None, claim_type="numeric",
            value=finding.value, unit=finding.unit,
        )])

    monkeypatch.setattr(service.adapter_registry, "execute", run_selected_task)
    monkeypatch.setattr(service, "_draft", grounded_draft)
    monkeypatch.setattr(assistant_router_module, "assistant_service", service)
    auth = _register(api_client, "assistant-partial-grounded@example.com")
    response = api_client.post("/assistant/chat", headers=_headers(auth), json={
        "message": "multi domain analysis",
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["execution"]["status"] == "partial"
    assert result["execution"]["tools"]["marketing"] == "failed"
    assert result["answer"] == "Calculated total records inspected: 4 count."
    assert result["answer_evidence_ids"] == ["data_quality"]


def test_malformed_draft_and_attempted_fallback_trust_bypass_are_rejected(api_client, monkeypatch):
    class MalformedDraftRouter(FakeOpenRouter):
        async def chat_completion(self, messages, **kwargs):
            if "Classify the user's current" in messages[0]["content"]:
                return json.dumps({"intent": "data_quality", "requested_domains": []})
            return "not-json"

    class ForgedTrustRouter(FakeOpenRouter):
        async def chat_completion(self, messages, **kwargs):
            if "Classify the user's current" in messages[0]["content"]:
                return json.dumps({"intent": "data_quality", "requested_domains": []})
            return json.dumps({
                "answer": "I have no verified data.",
                "response_origin": "trusted_system_fallback",
                "claims": [],
            })

    auth = _register(api_client, "assistant-forged-fallback@example.com")
    for llm in (MalformedDraftRouter(), ForgedTrustRouter()):
        monkeypatch.setattr(assistant_router_module, "assistant_service",
                            assistant_router_module.BusinessAssistantService(llm))
        response = api_client.post("/assistant/chat", headers=_headers(auth), json={"message": "quality"})
        assert response.status_code == 503
        assert "I have no verified data" not in response.text


def test_assistant_rejects_invalid_period_from_classifier(api_client, monkeypatch):
    class InvalidRange(FakeOpenRouter):
        async def chat_completion(self, messages, **kwargs):
            if "Classify the user's current" in messages[0]["content"]:
                return '{"intent":"profitability","start_date":"2026-10-01","end_date":"2026-09-01"}'
            return await super().chat_completion(messages, **kwargs)

    monkeypatch.setattr(assistant_router_module, "assistant_service",
                        assistant_router_module.BusinessAssistantService(InvalidRange()))
    auth = _register(api_client, "assistant-dates@example.com")
    response = api_client.post("/assistant/chat", headers=_headers(auth), json={"message": "profit"})
    assert response.status_code == 503
