"""Deterministic, sequential scheduler for validated request-local task plans."""

from app.schemas.coordination_schema import (
    CoordinationPlan,
    SharedFindingsContext,
    TaskExecutionContext,
    TaskResult,
)


def _set_status(plan: CoordinationPlan, task_id: str, status: str) -> CoordinationPlan:
    tasks = [
        task.model_copy(update={"status": status}) if task.task_id == task_id else task
        for task in plan.tasks
    ]
    return plan.model_copy(update={"tasks": tasks})


def _record_skip(
    plan: CoordinationPlan,
    shared: SharedFindingsContext,
    task,
    error_code: str,
) -> tuple[CoordinationPlan, SharedFindingsContext]:
    plan = _set_status(plan, task.task_id, "skipped")
    shared = shared.with_task_result(TaskResult(
        task_id=task.task_id,
        domain=task.domain,
        status="skipped",
        safe_error_code=error_code,
        attempt_count=0,
    ))
    return plan, shared


def next_ready_task(
    plan: CoordinationPlan,
    shared: SharedFindingsContext,
    *,
    profitability_investigation: bool = False,
) -> tuple[CoordinationPlan, SharedFindingsContext, str | None, TaskExecutionContext]:
    """Return the next runnable task, explicitly skipping blocked or unwarranted work."""
    tasks_by_id = {task.task_id: task for task in plan.tasks}
    for task in plan.tasks:
        if task.status != "pending" or task.task_id in shared.task_results:
            continue
        dependency_statuses = {
            dependency_id: tasks_by_id[dependency_id].status
            for dependency_id in task.dependency_task_ids
        }
        terminal_statuses = {"succeeded", "failed", "skipped"}
        # Optional dependencies affect whether declared findings are available,
        # so wait for them just as we do required dependencies. Their outcome
        # only affects whether the dependent task is blocked, not its readiness.
        if any(status not in terminal_statuses for status in dependency_statuses.values()):
            continue

        required_dependencies = set(task.dependency_task_ids) - set(task.optional_dependency_task_ids)
        if any(dependency_statuses[dependency_id] in {"failed", "skipped"}
               for dependency_id in required_dependencies):
            plan, shared = _record_skip(plan, shared, task, "dependency_failed")
            continue

        if profitability_investigation and task.task_id != "profitability":
            trend = shared.findings.get("profitability:net_profit_trend")
            if (
                trend is None
                or trend.evidence_status not in {"verified", "estimated"}
                or not isinstance(trend.value, dict)
                or trend.value.get("status") != "comparable"
                or trend.value.get("direction") != "decrease"
            ):
                plan, shared = _record_skip(plan, shared, task, "investigation_not_warranted")
                continue

        available_findings = []
        unavailable_ids = []
        for requirement in task.finding_requirements:
            finding = shared.findings.get(requirement.finding_id)
            result = shared.task_results.get(requirement.source_task_id)
            source_task = tasks_by_id[requirement.source_task_id]
            valid = (
                finding is not None
                and result is not None
                and result.status == "succeeded"
                and requirement.finding_id in result.finding_ids
                and finding.domain == source_task.domain
                and finding.evidence_status not in {"unavailable", "conflicting"}
            )
            if valid:
                available_findings.append(finding)
            else:
                unavailable_ids.append(requirement.finding_id)
        execution_context = TaskExecutionContext(
            findings=available_findings,
            unavailable_finding_ids=unavailable_ids,
        )
        plan = _set_status(plan, task.task_id, "running")
        return plan, shared, task.task_id, execution_context

    return plan, shared, None, TaskExecutionContext()
