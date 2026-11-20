import json
import logging
import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agents.context import AgentContext
from app.agents.errors import AgentError
from app.ai_engine.business_assistant_graph import build_business_assistant_graph
from app.llm.errors import OpenRouterError
from app.models.assistant_conversation_model import AssistantConversation, AssistantMessage
from app.schemas.assistant_schema import (
    AssistantChatRequest, AssistantChatResponse, AssistantDraft, AssistantExecutionSummary, AssistantIntent,
)
from app.services.anomaly_detection_service import AnomalyDetectionService
from app.ai_engine.task_adapters import TaskAdapterRegistry
from app.ai_engine.execution_budget import RequestBudgetExceeded, RequestExecutionBudget
from app.ai_engine.provider_data import project_provider_evidence, sanitize_provider_facts
from app.core.config import settings

logger = logging.getLogger("norfae_os.assistant")
MAX_CONTEXT_MESSAGES = 10
MAX_FACTS_CHARS = 14000


class AssistantProviderFailure(AgentError):
    pass


class AssistantNotFound(AgentError):
    pass


class BusinessAssistantService:
    """Fixed-tool, tenant-scoped assistant over existing deterministic services."""

    def __init__(self, openrouter, anomaly_service=None):
        self.openrouter = openrouter
        self.anomaly_service = anomaly_service or AnomalyDetectionService()
        self.adapter_registry = TaskAdapterRegistry()
        self.graph = build_business_assistant_graph(self)

    async def chat(self, db: Session, context: AgentContext, payload: AssistantChatRequest):
        business_id = int(context.require_business_scope("analytics:read"))
        if not context.user_id:
            raise ValueError("Authenticated user scope is required.")
        user_id = int(context.user_id)
        conversation = None
        if payload.conversation_id is not None:
            conversation = db.query(AssistantConversation).filter(
                AssistantConversation.id == payload.conversation_id,
                AssistantConversation.business_id == business_id,
                AssistantConversation.user_id == user_id,
            ).first()
            if conversation is None:
                raise AssistantNotFound

        history = []
        if conversation:
            history = db.query(AssistantMessage).filter(
                AssistantMessage.conversation_id == conversation.id,
                AssistantMessage.business_id == business_id,
            ).order_by(AssistantMessage.id.desc()).limit(MAX_CONTEXT_MESSAGES).all()
            history.reverse()

        # The graph's synchronous adapters use independent worker-owned sessions.
        # End the history read transaction first so it does not hold a connection
        # while a worker needs one (notably important with small connection pools).
        conversation_id = conversation.id if conversation is not None else None
        history_context = [
            {"role": row.role, "content": row.content[:2000]} for row in history
        ]
        db.rollback()

        execution_id = uuid4().hex
        execution_budget = RequestExecutionBudget(execution_id)
        state = await self.graph.ainvoke(
            {
                "execution_id": execution_id,
                "question": payload.message,
                "user_id": str(user_id),
                "business_id": business_id,
                "context": context,
                "db": db,
                "history": history_context,
                "execution_budget": execution_budget,
            },
            config={"recursion_limit": 24},
        )
        if state.get("failure_code"):
            raise AssistantProviderFailure
        intent_name = state.get("intent", "unsupported")
        draft: AssistantDraft = state["draft"]
        facts = self._compact_facts(state.get("facts", {}))
        limitations = self._limitations(facts)

        if conversation_id is not None:
            conversation = db.query(AssistantConversation).filter(
                AssistantConversation.id == conversation_id,
                AssistantConversation.business_id == business_id,
                AssistantConversation.user_id == user_id,
            ).first()
            if conversation is None:
                raise AssistantNotFound

        if conversation is None:
            title = " ".join(payload.message.split())[:117]
            if len(payload.message) > 117:
                title += "..."
            conversation = AssistantConversation(
                business_id=business_id, user_id=user_id, title=title or "Business question",
            )
            db.add(conversation)
            db.flush()
        db.add(AssistantMessage(
            business_id=business_id, conversation_id=conversation.id,
            role="user", content=payload.message,
        ))
        db.add(AssistantMessage(
            business_id=business_id, conversation_id=conversation.id,
            role="assistant", content=draft.answer,
        ))
        conversation.updated_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()
        db.refresh(conversation)
        execution = AssistantExecutionSummary(
            execution_id=execution_id,
            status=state["graph_status"],
            nodes_executed=state.get("nodes_executed", []),
            tools=state.get("tools", {}),
            errors=state.get("errors", []),
        )
        logger.info(
            "Assistant graph execution completed",
            extra={
                "execution_id": execution_id,
                "intent": intent_name,
                "graph_status": execution.status,
                "nodes_executed": execution.nodes_executed,
                "tools": execution.tools,
                "errors": execution.errors,
                **execution_budget.summary(state.get("coordination_plan")),
            },
        )
        return AssistantChatResponse(
            conversation_id=conversation.id,
            intent=intent_name,
            answer=draft.answer,
            answer_evidence_ids=draft.answer_evidence_ids,
            verified_facts=facts,
            interpretation=draft.interpretation,
            recommendations=draft.recommendations,
            unknowns=draft.unknowns,
            limitations=limitations,
            execution=execution,
        )

    @property
    def task_timeout_seconds(self):
        return settings.ASSISTANT_TASK_TIMEOUT_SECONDS

    @property
    def task_max_retries(self):
        return settings.ASSISTANT_TASK_MAX_RETRIES

    @property
    def retry_base_seconds(self):
        return settings.ASSISTANT_RETRY_BASE_SECONDS

    @property
    def retry_max_seconds(self):
        return settings.ASSISTANT_RETRY_MAX_SECONDS

    async def _classify(self, message, history, budget=None):
        prior = []
        for row in history[-MAX_CONTEXT_MESSAGES:]:
            role = row.get("role") if isinstance(row, dict) else row.role
            content = row.get("content") if isinstance(row, dict) else row.content
            # Prior assistant messages contain business results; intent routing
            # needs the user's conversational context, not those result payloads.
            if role != "user":
                continue
            prior.append({"role": role, "content": content[:2000]})
        prompt = [
            {"role": "system", "content": (
                "Classify the user's current business question into exactly one intent: "
                "profitability, products, cities, marketing, creatives, anomalies, overview, "
                "recommendations, data_quality, multi_domain, unsupported. Use recent conversation only to "
                "resolve references such as 'those products'. Return ONLY JSON with keys intent, "
                "start_date, end_date, requested_domains. requested_domains must be a list chosen only from "
                "profitability, products, cities, marketing, creatives, anomalies, data_quality; include only "
                "additional domains needed for this question. Use multi_domain for explicit cross-domain requests. "
                "For an investigation asking why a metric changed, include only relevant possible contributing "
                "domains; never imply correlation proves cause. Dates are YYYY-MM-DD or null. Never provide IDs, "
                "SQL, permissions, or business facts. If a date range is unclear, use null dates."
            )},
            *prior,
            {"role": "user", "content": message},
        ]
        text = await self._completion(prompt, max_tokens=200, budget=budget)
        try:
            return AssistantIntent.model_validate_json(self._json_object(text))
        except (ValidationError, ValueError, TypeError) as error:
            logger.warning("Assistant intent output failed validation (%s)", type(error).__name__)
            raise AssistantProviderFailure from None

    async def _draft(self, question, history, facts, tool_status, errors, budget=None,
                     evidence_findings=None, evidence_conflicts=None):
        provider_facts = sanitize_provider_facts(facts)
        provider_evidence = project_provider_evidence(
            evidence_findings or [], evidence_conflicts or [],
        )
        prompt_facts = self._bounded_prompt_facts(provider_facts)
        facts_text = json.dumps(prompt_facts, ensure_ascii=False, separators=(",", ":"), default=str)
        prompt = [
            {"role": "system", "content": (
                "Answer using ONLY the supplied business results and validated evidence records. "
                "OBSERVED means directly recorded; CALCULATED means deterministic calculation; "
                "INFERRED is interpretation and must never be presented as a direct observation; "
                "UNAVAILABLE means missing or insufficient data. Do not calculate metrics, "
                "fill missing/null values, infer causes, or claim unsupported facts. Clearly label "
                "interpretations. If evidence is missing, say so. Discuss conflict reports using "
                "their deterministic category and outcome; never override or resolve them yourself. "
                "Different metric names are not contradictions. Do not put factual assertions in "
                "answer, interpretation, or recommendation prose: final factual text is rendered "
                "from validated structured claims. Return ONLY JSON with answer (string, ignored "
                "for display), answer_evidence_ids (array, ignored), interpretation (string, ignored), "
                "recommendations (empty array), unknowns (array), claims (up to 12 objects with "
                "claim_id, text, finding_ids, domain, metric_name, period_start, period_end, "
                "claim_type, value, unit), and recommendation_intents (up to 5 objects with "
                "action and finding_ids). Claim finding_ids must name exact opaque IDs from "
                "validated_evidence; use each finding's metric_name alias (not metric_label). "
                "Domain, metric_name, period, unit, and value must exactly match projected findings. "
                "Use numeric only for a single exact numeric metric value; do not calculate or "
                "reformat numbers. Use qualitative only when its value exactly matches a finding. "
                "Allowed recommendation actions: review_metric, collect_data, compare_periods. "
                "Never cite a conflict or unavailable value as established. Do not include IDs or "
                "personal information beyond supplied findings."
            )},
            *[
                {
                    "role": row.get("role") if isinstance(row, dict) else row.role,
                    "content": (row.get("content") if isinstance(row, dict) else row.content)[:2000],
                }
                for row in history[-MAX_CONTEXT_MESSAGES:]
                if (row.get("role") if isinstance(row, dict) else row.role) == "user"
            ],
            {"role": "user", "content": "Question: " + question + "\nverified_facts: " + facts_text
             + "\ntool_status: " + json.dumps(tool_status, separators=(",", ":"))
             + "\ntool_errors: " + json.dumps(errors, separators=(",", ":"))
             + "\nvalidated_evidence: " + json.dumps([
                 finding for finding in provider_evidence.findings[:60]
             ], ensure_ascii=False, separators=(",", ":"), default=str)
             + "\nevidence_conflicts: " + json.dumps([
                 conflict for conflict in provider_evidence.conflicts[:30]
             ], ensure_ascii=False, separators=(",", ":"), default=str)
             },
        ]
        text = await self._completion(prompt, max_tokens=900, budget=budget)
        try:
            draft = AssistantDraft.model_validate_json(self._json_object(text))
        except (ValidationError, ValueError, TypeError) as error:
            locations = [".".join(str(part) for part in issue.get("loc", ())) for issue in error.errors()] \
                if isinstance(error, ValidationError) else []
            logger.warning("Assistant draft output failed validation (%s; fields=%s)",
                           type(error).__name__, locations)
            raise AssistantProviderFailure from None
        return provider_evidence.restore_draft_references(draft)

    async def _completion(self, messages, *, max_tokens, budget=None):
        try:
            if budget:
                budget.reserve_llm_call()
                async with asyncio.timeout(budget.remaining_seconds()):
                    result = await self.openrouter.chat_completion(messages, temperature=0, max_tokens=max_tokens)
            else:
                result = await self.openrouter.chat_completion(messages, temperature=0, max_tokens=max_tokens)
        except RequestBudgetExceeded:
            raise
        except TimeoutError:
            raise RequestBudgetExceeded("budget_exceeded") from None
        except OpenRouterError:
            logger.warning("Assistant LLM request failed", extra={"error_type": "provider"})
            raise AssistantProviderFailure from None
        if not isinstance(result, str) or not result.strip():
            raise AssistantProviderFailure
        return result.strip()

    @staticmethod
    def _json_object(text):
        value = text.strip()
        if value.startswith("```"):
            value = value.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("Expected JSON object")
        return value

    @staticmethod
    def _period(intent):
        end = intent.end_date or date.today()
        start = intent.start_date or end - timedelta(days=29)
        if start > end:
            raise ValueError("start_date must be on or before end_date.")
        return start, end

    @staticmethod
    def _unsupported_draft():
        return AssistantDraft(
            answer="I can help analyze business profitability, products, cities, marketing, creatives, anomalies, business overviews, and data quality. Please ask a question in one of those areas."
        )

    @staticmethod
    def _unavailable_draft(domains, errors):
        return AssistantDraft(
            answer="I could not retrieve verified results for this request. Check the execution status and try again later.",
            interpretation="",
            recommendations=[],
            unknowns=[f"No verified result was available for: {', '.join(domains) or 'the selected analysis'}.", *errors],
        )

    @staticmethod
    def _budget_limited_draft(evidence_ids):
        return AssistantDraft(
            answer="The response-generation budget was reached. Review execution status and any validated results below.",
            answer_evidence_ids=evidence_ids,
            interpretation="",
            recommendations=[],
            unknowns=["A narrative response could not be generated within the request budget."],
        )

    @staticmethod
    def _limitations(facts):
        warnings = []
        def visit(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"warnings", "insufficient_data", "unknowns"} and isinstance(item, list):
                        warnings.extend(str(entry) for entry in item)
                    else:
                        visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
        visit(facts)
        return list(dict.fromkeys(warnings))[:30]

    @staticmethod
    def _compact_facts(value):
        """Bound model context and API facts while keeping nested data valid."""
        if isinstance(value, dict):
            return {key: BusinessAssistantService._compact_facts(item) for key, item in value.items()}
        if isinstance(value, list):
            return [BusinessAssistantService._compact_facts(item) for item in value[:15]]
        if isinstance(value, str):
            return value[:500]
        return value

    @staticmethod
    def _bounded_prompt_facts(facts):
        """Trim large result collections without creating invalid JSON fragments."""
        for list_limit, string_limit in ((12, 500), (6, 250), (3, 120), (1, 40), (0, 20)):
            def compact(value):
                if isinstance(value, dict):
                    return {key: compact(item) for key, item in value.items()}
                if isinstance(value, list):
                    return [compact(item) for item in value[:list_limit]]
                if isinstance(value, str):
                    return value[:string_limit]
                return value

            bounded = compact(facts)
            if len(json.dumps(bounded, ensure_ascii=False, separators=(",", ":"), default=str)) <= MAX_FACTS_CHARS:
                return bounded
        return {"evidence_keys": list(facts)[:10], "note": "Detailed results exceeded the model context limit."}
