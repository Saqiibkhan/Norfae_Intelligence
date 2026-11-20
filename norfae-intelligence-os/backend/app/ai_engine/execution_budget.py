"""Request-local attempt, time, LLM-call, and safe trace budgets."""

from __future__ import annotations

from datetime import UTC, datetime
from time import monotonic
from typing import Any

from app.core.config import settings


class RequestBudgetExceeded(Exception):
    def __init__(self, safe_code: str = "budget_exceeded"):
        self.safe_code = safe_code
        super().__init__(safe_code)


class RequestExecutionBudget:
    def __init__(self, execution_id: str):
        self.execution_id = execution_id
        self._started_monotonic = monotonic()
        self._deadline = self._started_monotonic + settings.ASSISTANT_REQUEST_TIMEOUT_SECONDS
        self._max_task_attempts = settings.ASSISTANT_MAX_TASK_ATTEMPTS
        self._max_llm_calls = settings.ASSISTANT_MAX_LLM_CALLS
        self.total_attempts = 0
        self.llm_calls = 0
        self.tasks_planned = 0
        self._tasks: dict[str, dict[str, Any]] = {}

    def remaining_seconds(self) -> float:
        return max(0.0, self._deadline - monotonic())

    @property
    def is_expired(self) -> bool:
        return self.remaining_seconds() <= 0

    @property
    def can_start_task(self) -> bool:
        return not self.is_expired and self.total_attempts < self._max_task_attempts

    def reserve_llm_call(self) -> None:
        if self.is_expired:
            raise RequestBudgetExceeded("budget_exceeded")
        if self.llm_calls >= self._max_llm_calls:
            raise RequestBudgetExceeded("budget_exceeded")
        self.llm_calls += 1

    def begin_task_attempt(self, task, dependency_status: dict[str, str]) -> int:
        if self.is_expired or self.total_attempts >= self._max_task_attempts:
            raise RequestBudgetExceeded("budget_exceeded")
        now = datetime.now(UTC)
        task_trace = self._tasks.get(task.task_id)
        if task_trace is None:
            task_trace = {
                "execution_id": self.execution_id,
                "task_id": task.task_id,
                "domain": task.domain,
                "started_at": now,
                "ended_at": None,
                "duration_ms": None,
                "attempt_count": 0,
                "final_status": "running",
                "safe_error_code": None,
                "dependency_status": dict(dependency_status),
                "attempts": [],
                "_started_monotonic": monotonic(),
            }
            self._tasks[task.task_id] = task_trace
        task_trace["attempt_count"] += 1
        self.total_attempts += 1
        task_trace["attempts"].append({
            "attempt": task_trace["attempt_count"],
            "started_at": now,
            "ended_at": None,
            "duration_ms": None,
            "status": "running",
            "safe_error_code": None,
        })
        return task_trace["attempt_count"]

    def finish_task_attempt(self, task_id: str, status: str, safe_error_code: str | None = None) -> None:
        task_trace = self._tasks[task_id]
        attempt = task_trace["attempts"][-1]
        ended = datetime.now(UTC)
        attempt["ended_at"] = ended
        attempt["duration_ms"] = max(0.0, (ended - attempt["started_at"]).total_seconds() * 1000)
        attempt["status"] = status
        attempt["safe_error_code"] = safe_error_code

    def finish_task(self, task_id: str, status: str, safe_error_code: str | None = None) -> None:
        task_trace = self._tasks[task_id]
        ended = datetime.now(UTC)
        task_trace["ended_at"] = ended
        task_trace["duration_ms"] = max(0.0, (ended - task_trace["started_at"]).total_seconds() * 1000)
        task_trace["final_status"] = status
        task_trace["safe_error_code"] = safe_error_code

    def record_skipped(self, task, dependency_status: dict[str, str], safe_error_code: str | None) -> None:
        if task.task_id in self._tasks:
            return
        now = datetime.now(UTC)
        self._tasks[task.task_id] = {
            "execution_id": self.execution_id,
            "task_id": task.task_id,
            "domain": task.domain,
            "started_at": now,
            "ended_at": now,
            "duration_ms": 0.0,
            "attempt_count": 0,
            "final_status": "skipped",
            "safe_error_code": safe_error_code,
            "dependency_status": dict(dependency_status),
            "attempts": [],
        }

    def task_attempt_count(self, task_id: str) -> int:
        return self._tasks.get(task_id, {}).get("attempt_count", 0)

    @property
    def task_traces(self) -> list[dict[str, Any]]:
        return [
            {key: value for key, value in trace.items() if not key.startswith("_")}
            for trace in self._tasks.values()
        ]

    def summary(self, plan) -> dict[str, Any]:
        statuses = [task.status for task in plan.tasks] if plan is not None else []
        return {
            "execution_id": self.execution_id,
            "total_duration_ms": max(0.0, (monotonic() - self._started_monotonic) * 1000),
            "tasks_planned": self.tasks_planned or len(statuses),
            "tasks_succeeded": statuses.count("succeeded"),
            "tasks_failed": statuses.count("failed"),
            "tasks_skipped": statuses.count("skipped"),
            "total_attempts": self.total_attempts,
            "llm_calls": self.llm_calls,
            "task_traces": self.task_traces,
        }
