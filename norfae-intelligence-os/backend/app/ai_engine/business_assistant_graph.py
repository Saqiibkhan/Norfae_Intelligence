"""Request-scoped LangGraph orchestration for the Business Assistant."""

import logging
import time
import asyncio
from typing import Any, Literal, TypedDict

from app.ai_engine.xxhash_compat import install_xxhash_fallback

XXHASH_FALLBACK_ACTIVE = install_xxhash_fallback()

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.context import AgentContext
from app.ai_engine.task_adapters import TaskAdapterError
from app.ai_engine.coordination_scheduler import next_ready_task
from app.ai_engine.finding_extraction import extract_findings
from app.ai_engine.execution_budget import RequestBudgetExceeded
from app.ai_engine.evidence_validation import (
    EvidenceConflict, detect_evidence_conflicts, enforce_conflict_policy,
    ground_assistant_draft, validate_shared_evidence,
)
from app.schemas.assistant_schema import AssistantIntent
from app.schemas.coordination_schema import (
    CoordinationPlan,
    CoordinationTask,
    FindingRequirement,
    SharedFindingsContext,
    TaskExecutionContext,
    TaskResult,
)

logger = logging.getLogger("norfae_os.assistant.graph")

DOMAINS = (
    "profitability", "products", "cities", "marketing", "creatives",
    "anomalies", "data_quality",
)
DOMAIN_NODES = {domain: f"execute_{domain}" for domain in DOMAINS}
OVERVIEW_DOMAINS = ["profitability", "products", "cities", "marketing", "anomalies"]


class AssistantGraphState(TypedDict, total=False):
    execution_id: str
    question: str
    user_id: str
    business_id: int
    context: AgentContext
    db: Session
    history: list[dict[str, str]]
    intent: str
    start_date: Any
    end_date: Any
    requested_domains: list[str]
    selected_domains: list[str]
    current_task_id: str | None
    current_task_domain: str | None
    task_execution_context: TaskExecutionContext
    profitability_investigation: bool
    domain_results: dict[str, dict[str, Any]]
    facts: dict[str, Any]
    tools: dict[str, Literal["success", "failed", "skipped"]]
    errors: list[str]
    nodes_executed: list[str]
    draft: Any
    graph_status: Literal["complete", "partial", "failed", "unsupported"]
    failure_code: str | None
    answer_evidence_ids: list[str]
    coordination_plan: CoordinationPlan
    shared_findings: SharedFindingsContext
    execution_budget: Any
    validated_findings: list[Any]
    evidence_conflicts: list[EvidenceConflict]
    response_origin: Literal["llm_claims", "trusted_system_fallback", "deterministic"]


def _node(state: AssistantGraphState, name: str, **updates):
    return {**updates, "nodes_executed": [*state.get("nodes_executed", []), name]}


def _set_plan_task_status(plan: CoordinationPlan, task_id: str, status: str) -> CoordinationPlan:
    tasks = [
        task.model_copy(update={"status": status}) if task.task_id == task_id else task
        for task in plan.tasks
    ]
    return plan.model_copy(update={"tasks": tasks})


def _is_profitability_investigation(question: str) -> bool:
    import re

    return bool(re.search(
        r"\b(why|declin\w*|decreas\w*|drop\w*|fell|fall\w*|down)\b",
        question.casefold(),
    ))


def build_coordination_plan(
    *, intent: str, requested_domains: list[str], question: str,
    start_date, end_date, execution_id: str,
) -> tuple[CoordinationPlan, list[str], bool]:
    """Build a fixed allowlisted plan; the classifier cannot provide task IDs or code."""
    investigation = intent == "profitability" and _is_profitability_investigation(question)
    extras = [domain for domain in requested_domains if domain in DOMAINS]
    if investigation:
        domains = ["profitability", "products", "cities", "marketing", "anomalies"]
    elif intent in {"overview", "recommendations"}:
        domains = list(OVERVIEW_DOMAINS)
    elif intent == "multi_domain":
        domains = extras or list(OVERVIEW_DOMAINS)
    elif intent in DOMAINS:
        domains = [intent, *extras]
    else:
        domains = []
    domains = list(dict.fromkeys(domain for domain in domains if domain in DOMAINS))[:len(DOMAINS)]

    tasks = []
    for domain in domains:
        dependencies = ["profitability"] if investigation and domain != "profitability" else []
        tasks.append(CoordinationTask(
            task_id=domain,
            domain=domain,
            status="pending",
            dependency_task_ids=dependencies,
            finding_requirements=(
                [FindingRequirement(
                    source_task_id="profitability",
                    finding_id="profitability:net_profit_trend",
                )]
                if dependencies else []
            ),
            parameters=(
                {} if domain == "data_quality"
                else {"start_date": start_date, "end_date": end_date}
            ),
        ))
    return CoordinationPlan(plan_id=execution_id, tasks=tasks, status="running"), domains, investigation


def _coordination_result(value: Any):
    """Copy service output without identity, authorization, or secret fields."""
    forbidden = {
        "userid", "businessid", "tenantid", "accesstoken", "refreshtoken",
        "apikey", "apitoken", "integrationtoken", "clientsecret", "token", "secret", "password", "credential",
        "credentials", "authorization", "permissions",
    }
    if isinstance(value, dict):
        return {
            key: _coordination_result(item)
            for key, item in value.items()
            if "".join(character for character in str(key).casefold() if character.isalnum()) not in forbidden
        }
    if isinstance(value, list):
        return [_coordination_result(item) for item in value]
    return value


def build_business_assistant_graph(service):
    """Compile an immutable graph; all business/request data lives in invocation state."""

    async def validate_input(state: AssistantGraphState):
        context = state["context"]
        trusted_business_id = int(context.require_business_scope("analytics:read"))
        trusted_user_id = int(context.user_id or "0")
        request_user_id = int(state.get("user_id", "0"))
        if (
            trusted_user_id <= 0
            or trusted_user_id != request_user_id
            or trusted_business_id != state["business_id"]
        ):
            return _node(
                state, "validate_input", graph_status="failed",
                errors=["trusted_context_invalid"], failure_code="trusted_context_invalid",
            )
        return _node(
            state, "validate_input", user_id=str(trusted_user_id),
            business_id=trusted_business_id, graph_status="complete",
            errors=[], tools={domain: "skipped" for domain in DOMAINS},
            domain_results={}, facts={}, shared_findings=SharedFindingsContext(),
            response_origin="llm_claims",
        )

    def route_after_input(state: AssistantGraphState) -> str:
        return "provider_failure" if state.get("failure_code") else "classify_intent"

    async def classify_intent(state: AssistantGraphState):
        try:
            intent: AssistantIntent = await service._classify(
                state["question"], state.get("history", []), state.get("execution_budget"),
            )
        except Exception as error:
            logger.warning(
                "Assistant intent classification failed (%s)", type(error).__name__,
                extra={"execution_id": state["execution_id"], "error_type": type(error).__name__},
            )
            return _node(
                state, "classify_intent", graph_status="failed",
                errors=["intent_classification_failed"], failure_code="llm_unavailable",
            )
        return _node(
            state, "classify_intent", intent=intent.intent,
            start_date=intent.start_date, end_date=intent.end_date,
            requested_domains=intent.requested_domains,
        )

    def route_after_classification(state: AssistantGraphState) -> str:
        if state.get("failure_code"):
            return "provider_failure"
        if state.get("intent") == "unsupported":
            return "unsupported_response"
        return "plan_tasks"

    async def plan_tasks(state: AssistantGraphState):
        intent = state["intent"]
        start_date, end_date = service._period(
            AssistantIntent(intent=intent, start_date=state.get("start_date"), end_date=state.get("end_date"))
        )
        tools = dict(state.get("tools", {}))
        plan, domains, investigation = build_coordination_plan(
            intent=intent,
            requested_domains=state.get("requested_domains", []),
            question=state["question"],
            start_date=start_date,
            end_date=end_date,
            execution_id=state["execution_id"],
        )
        for domain in domains:
            tools[domain] = "skipped"
        if state.get("execution_budget"):
            state["execution_budget"].tasks_planned = len(plan.tasks)
        return _node(
            state, "plan_tasks", selected_domains=domains,
            start_date=start_date, end_date=end_date, tools=tools, coordination_plan=plan,
            profitability_investigation=investigation,
        )

    def schedule_tasks(state: AssistantGraphState):
        budget = state.get("execution_budget")
        plan = state["coordination_plan"]
        shared = state["shared_findings"]
        if budget and not budget.can_start_task:
            for pending in plan.tasks:
                if pending.status != "pending":
                    continue
                plan = _set_plan_task_status(plan, pending.task_id, "skipped")
                shared = shared.with_task_result(TaskResult(
                    task_id=pending.task_id, domain=pending.domain, status="skipped",
                    safe_error_code="budget_exceeded", attempt_count=0,
                ))
                budget.record_skipped(pending, {
                    dep: next(item.status for item in plan.tasks if item.task_id == dep)
                    for dep in pending.dependency_task_ids
                }, "budget_exceeded")
            task_id, execution_context = None, TaskExecutionContext()
        else:
            previous = {item.task_id: item.status for item in plan.tasks}
            plan, shared, task_id, execution_context = next_ready_task(
            state["coordination_plan"], state["shared_findings"],
            profitability_investigation=state.get("profitability_investigation", False),
            )
            if budget:
                for skipped in plan.tasks:
                    if previous.get(skipped.task_id) == "pending" and skipped.status == "skipped":
                        result = shared.task_results.get(skipped.task_id)
                        deps = {dep: next(item.status for item in plan.tasks if item.task_id == dep)
                                for dep in skipped.dependency_task_ids}
                        budget.record_skipped(skipped, deps, result.safe_error_code if result else None)
        task = next((item for item in plan.tasks if item.task_id == task_id), None)
        return _node(
            state, "schedule_tasks", coordination_plan=plan, shared_findings=shared,
            current_task_id=task_id, current_task_domain=task.domain if task else None,
            task_execution_context=execution_context,
        )

    def route_after_scheduling(state: AssistantGraphState) -> str:
        domain = state.get("current_task_domain")
        return DOMAIN_NODES[domain] if domain in DOMAIN_NODES else "validate_results"

    def make_tool_node(domain: str):
        async def execute_domain(state: AssistantGraphState):
            task_id = state.get("current_task_id")
            if not task_id or state.get("current_task_domain") != domain:
                return _node(state, f"execute_{domain}")
            started_at = time.monotonic()
            budget = state.get("execution_budget")
            task = next(task for task in state["coordination_plan"].tasks if task.task_id == task_id)
            dependency_status = {
                dep: next(item.status for item in state["coordination_plan"].tasks if item.task_id == dep)
                for dep in task.dependency_task_ids
            }
            attempts = 0
            try:
                while True:
                    if budget:
                        attempts = budget.begin_task_attempt(task, dependency_status)
                    else:
                        attempts += 1
                    try:
                        remaining = budget.remaining_seconds() if budget else None
                        if remaining is not None and remaining <= 0:
                            raise TaskAdapterError("BUDGET_EXCEEDED")
                        output = await service.adapter_registry.execute(
                            task, state["context"], state["task_execution_context"],
                            timeout_seconds=min(remaining, service.task_timeout_seconds) if remaining else None,
                        )
                        if budget:
                            budget.finish_task_attempt(task_id, "succeeded")
                        break
                    except TaskAdapterError as attempt_error:
                        retry_limit = service.task_max_retries
                        if budget:
                            budget.finish_task_attempt(task_id, "failed", attempt_error.category.lower())
                        if attempt_error.category != "TRANSIENT_FAILURE" or attempts > retry_limit:
                            raise
                        try:
                            state["db"].rollback()
                        except Exception:
                            pass
                        delay = min(service.retry_base_seconds * (2 ** (attempts - 1)), service.retry_max_seconds)
                        if budget and budget.remaining_seconds() <= delay:
                            raise
                        await asyncio.sleep(delay)
                result = output.model_dump(mode="json")
                findings = extract_findings(task_id, domain, output)
                results = dict(state.get("domain_results", {}))
                results[domain] = result
                tools = dict(state["tools"])
                tools[domain] = "success"
                shared_findings = state["shared_findings"]
                for finding in findings:
                    shared_findings = shared_findings.with_finding(finding)
                task_result = TaskResult(
                    task_id=task_id,
                    domain=domain,
                    status="succeeded",
                    result=_coordination_result(result),
                    duration_ms=max(0.0, (time.monotonic() - started_at) * 1000),
                    finding_ids=[finding.finding_id for finding in findings],
                    attempt_count=max(1, attempts),
                )
                if budget:
                    budget.finish_task(task_id, "succeeded")
                    logger.info("Assistant task completed", extra=budget.task_traces[-1])
                shared_findings = shared_findings.with_task_result(task_result)
                return _node(
                    state, f"execute_{domain}",
                    domain_results=results, tools=tools, shared_findings=shared_findings,
                    coordination_plan=_set_plan_task_status(state["coordination_plan"], task_id, "succeeded"),
                )
            except Exception as error:
                if isinstance(error, RequestBudgetExceeded) and attempts == 0:
                    shared = state["shared_findings"].with_task_result(TaskResult(
                        task_id=task_id, domain=domain, status="skipped",
                        safe_error_code="budget_exceeded", attempt_count=0,
                    ))
                    if budget:
                        budget.record_skipped(task, dependency_status, "budget_exceeded")
                    return _node(
                        state, f"execute_{domain}", shared_findings=shared,
                        tools={**state["tools"], domain: "skipped"},
                        coordination_plan=_set_plan_task_status(state["coordination_plan"], task_id, "skipped"),
                    )
                if budget:
                    if attempts == 0:
                        try:
                            attempts = budget.begin_task_attempt(task, dependency_status)
                            budget.finish_task_attempt(task_id, "failed", "budget_exceeded")
                        except RequestBudgetExceeded:
                            pass
                    try:
                        safe_code = (
                            error.category.lower() if isinstance(error, TaskAdapterError)
                            else "budget_exceeded" if isinstance(error, RequestBudgetExceeded)
                            else "task_execution_failed"
                        )
                        budget.finish_task(task_id, "failed", safe_code)
                    except KeyError:
                        pass
                try:
                    state["db"].rollback()
                except Exception:
                    pass
                logger.warning(
                    "Assistant analysis tool failed",
                    extra={
                        "execution_id": state["execution_id"],
                        "tool": domain,
                        "error_type": type(error).__name__,
                    },
                )
                tools = dict(state["tools"])
                tools[domain] = "failed"
                errors = [*state.get("errors", []), f"{domain}_tool_failed"]
                task_result = TaskResult(
                    task_id=task_id,
                    domain=domain,
                    status="failed",
                    safe_error_code=(error.category.lower() if isinstance(error, TaskAdapterError)
                                     else "budget_exceeded" if isinstance(error, RequestBudgetExceeded)
                                     else "task_execution_failed"),
                    duration_ms=max(0.0, (time.monotonic() - started_at) * 1000),
                    attempt_count=max(1, attempts),
                )
                if budget:
                    logger.info("Assistant task completed", extra=budget.task_traces[-1])
                shared_findings = state["shared_findings"].with_task_result(task_result)
                return _node(
                    state, f"execute_{domain}",
                    tools=tools, errors=errors, shared_findings=shared_findings,
                    coordination_plan=_set_plan_task_status(state["coordination_plan"], task_id, "failed"),
                )
        return execute_domain

    async def validate_results(state: AssistantGraphState):
        facts: dict[str, Any] = {}
        for domain in state.get("selected_domains", []):
            result = state.get("domain_results", {}).get(domain)
            if state.get("tools", {}).get(domain) == "success" and isinstance(result, dict):
                facts.update(result)
            elif state.get("tools", {}).get(domain) == "success":
                tools = dict(state["tools"])
                tools[domain] = "failed"
                errors = [*state.get("errors", []), f"{domain}_result_invalid"]
                return _node(state, "validate_results", facts=facts, tools=tools, errors=errors, graph_status="partial")
        task_statuses = [task.status for task in state.get("coordination_plan", CoordinationPlan(plan_id="empty", tasks=[])).tasks]
        succeeded = task_statuses.count("succeeded")
        failed = task_statuses.count("failed")
        budget_skips = any(
            result.status == "skipped" and result.safe_error_code == "budget_exceeded"
            for result in state.get("shared_findings", SharedFindingsContext()).task_results.values()
        )
        status = (
            "partial" if (failed or budget_skips) and succeeded
            else "failed" if failed or budget_skips
            else "complete"
        )
        plan = state.get("coordination_plan")
        if plan is not None:
            plan = plan.model_copy(update={"status": status})
        validation = validate_shared_evidence(state.get("shared_findings", SharedFindingsContext()))
        conflicts = detect_evidence_conflicts(validation.findings)
        errors = list(state.get("errors", []))
        if validation.invalid_finding_ids:
            logger.warning("Assistant evidence validation rejected findings", extra={
                "execution_id": state["execution_id"],
                "invalid_finding_count": len(validation.invalid_finding_ids),
                "validation_error_codes": validation.safe_errors,
            })
            errors.append("evidence_validation_failed")
        return _node(
            state, "validate_results", facts=facts, graph_status=status, coordination_plan=plan,
            validated_findings=validation.findings, evidence_conflicts=conflicts, errors=errors,
        )

    async def prepare_evidence(state: AssistantGraphState):
        return _node(state, "prepare_evidence", answer_evidence_ids=list(state.get("facts", {})))

    async def generate_response(state: AssistantGraphState):
        facts = state.get("facts", {})
        if not facts:
            return _node(
                state, "generate_response",
                draft=service._unavailable_draft(state.get("selected_domains", []), state.get("errors", [])),
                response_origin="trusted_system_fallback",
            )
        try:
            draft = await service._draft(
                state["question"], state.get("history", []), facts,
                state.get("tools", {}), state.get("errors", []),
                state.get("execution_budget"),
                state.get("validated_findings", []), state.get("evidence_conflicts", []),
            )
        except Exception as error:
            logger.warning(
                "Assistant response generation failed (%s)", type(error).__name__,
                extra={"execution_id": state["execution_id"], "error_type": type(error).__name__},
            )
            if isinstance(error, RequestBudgetExceeded):
                validated_refs = list(dict.fromkeys(
                    finding.evidence_ref
                    for finding in state.get("validated_findings", [])
                    if finding.evidence_ref in facts
                ))
                return _node(
                    state, "generate_response",
                    draft=service._budget_limited_draft(validated_refs[:8]),
                    response_origin="trusted_system_fallback",
                )
            return _node(
                state, "generate_response", graph_status="failed",
                failure_code="llm_unavailable", errors=[*state.get("errors", []), "response_generation_failed"],
            )
        return _node(state, "generate_response", draft=draft, response_origin="llm_claims")

    async def validate_response(state: AssistantGraphState):
        draft = state.get("draft")
        facts = state.get("facts", {})
        response_origin = state.get("response_origin", "llm_claims")
        if draft and response_origin == "llm_claims":
            draft = ground_assistant_draft(
                draft,
                state.get("shared_findings", SharedFindingsContext()),
                state.get("evidence_conflicts", []),
                set(facts),
            )
            draft = enforce_conflict_policy(
                draft,
                state.get("evidence_conflicts", []),
                state.get("validated_findings", []),
                set(facts),
            )
            response_origin = "deterministic"
        # Trusted fallbacks are created only by the graph's no-data and budget
        # branches. This marker is reset during validate_input, so it cannot be
        # supplied through request state or provider-generated draft JSON.
        return _node(state, "validate_response", draft=draft, response_origin=response_origin)

    async def unsupported_response(state: AssistantGraphState):
        return _node(
            state, "unsupported_response", graph_status="unsupported", facts={},
            tools={domain: "skipped" for domain in DOMAINS},
            draft=service._unsupported_draft(), answer_evidence_ids=[],
            response_origin="deterministic",
        )

    async def provider_failure(state: AssistantGraphState):
        return _node(state, "provider_failure", graph_status="failed")

    graph = StateGraph(AssistantGraphState)
    graph.add_node("validate_input", validate_input)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("plan_tasks", plan_tasks)
    graph.add_node("schedule_tasks", schedule_tasks)
    for domain in DOMAINS:
        graph.add_node(DOMAIN_NODES[domain], make_tool_node(domain))
    graph.add_node("validate_results", validate_results)
    graph.add_node("prepare_evidence", prepare_evidence)
    graph.add_node("generate_response", generate_response)
    graph.add_node("validate_response", validate_response)
    graph.add_node("unsupported_response", unsupported_response)
    graph.add_node("provider_failure", provider_failure)
    graph.add_edge(START, "validate_input")
    graph.add_conditional_edges(
        "validate_input", route_after_input,
        {"provider_failure": "provider_failure", "classify_intent": "classify_intent"},
    )
    graph.add_conditional_edges(
        "classify_intent", route_after_classification,
        {"provider_failure": "provider_failure", "unsupported_response": "unsupported_response", "plan_tasks": "plan_tasks"},
    )
    route_mapping = {**{node: node for node in DOMAIN_NODES.values()}, "validate_results": "validate_results"}
    graph.add_edge("plan_tasks", "schedule_tasks")
    graph.add_conditional_edges("schedule_tasks", route_after_scheduling, route_mapping)
    for node_name in DOMAIN_NODES.values():
        graph.add_edge(node_name, "schedule_tasks")
    graph.add_edge("validate_results", "prepare_evidence")
    graph.add_edge("prepare_evidence", "generate_response")
    graph.add_edge("generate_response", "validate_response")
    graph.add_edge("validate_response", END)
    graph.add_edge("unsupported_response", END)
    graph.add_edge("provider_failure", END)
    return graph.compile()
