"""Internal, request-scoped contracts for future intelligence coordination."""

import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.agents.city_intelligence import CityIntelligenceInput
from app.agents.data_analysis import DataAnalysisInput
from app.agents.marketing_intelligence import MarketingInput
from app.agents.product_intelligence import ProductIntelligenceInput
from app.agents.creative_intelligence import CreativeIntelligenceInput
from app.schemas.anomaly_schema import AnomalyQuery
from app.schemas.assistant_schema import AssistantDomain


CoordinationDomain = AssistantDomain
TaskExecutionStatus = Literal["pending", "running", "succeeded", "failed", "skipped"]
PlanStatus = Literal["draft", "ready", "running", "complete", "partial", "failed"]
EvidenceStatus = Literal["verified", "estimated", "unavailable", "conflicting"]
EvidenceClassification = Literal["OBSERVED", "CALCULATED", "INFERRED", "UNAVAILABLE"]
DataAvailability = Literal["available", "partial", "unavailable"]
SafeTaskErrorCode = Literal[
    "task_execution_failed", "task_timed_out", "task_result_invalid",
    "dependency_failed", "provider_unavailable", "result_validation_failed",
    "invalid_task", "unsupported_domain", "permission_denied", "data_unavailable",
    "validation_error", "transient_failure", "internal_error", "required_finding_missing",
    "investigation_not_warranted", "timeout", "budget_exceeded",
]

MAX_COORDINATION_TASKS = 14
MAX_FINDING_VALUE_CHARS = 20_000
_FORBIDDEN_CONTEXT_KEYS = {
    "userid", "businessid", "tenantid", "accesstoken", "refreshtoken",
    "apikey", "apitoken", "integrationtoken", "clientsecret", "token", "secret", "password", "credential",
    "credentials", "authorization", "permissions",
}


def _validate_context_value(value: Any, *, field_name: str):
    def visit(item):
        if isinstance(item, dict):
            for key, nested in item.items():
                normalized_key = "".join(character for character in str(key).casefold() if character.isalnum())
                if normalized_key in _FORBIDDEN_CONTEXT_KEYS:
                    raise ValueError(f"{field_name} cannot contain identity or credential fields.")
                visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    try:
        encoded = json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{field_name} must contain finite JSON-compatible data.") from None
    visit(value)
    if len(encoded) > MAX_FINDING_VALUE_CHARS:
        raise ValueError(f"{field_name} exceeds the supported size.")
    return value


class ReportingPeriod(BaseModel):
    start_date: date
    end_date: date

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_range(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date.")
        return self


class ProfitabilityTaskParameters(BaseModel):
    """Internal parameters for the existing deterministic profitability service."""

    start_date: date | None = None
    end_date: date | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_range(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date.")
        return self


_PARAMETER_MODELS: dict[str, type[BaseModel]] = {
    "profitability": ProfitabilityTaskParameters,
    "products": ProductIntelligenceInput,
    "cities": CityIntelligenceInput,
    "marketing": MarketingInput,
    "creatives": CreativeIntelligenceInput,
    "anomalies": AnomalyQuery,
    "data_quality": DataAnalysisInput,
}


class CoordinationTask(BaseModel):
    task_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$")
    domain: CoordinationDomain
    priority: int = Field(default=3, ge=1, le=5, description="1 is highest priority; 5 is lowest.")
    dependency_task_ids: list[str] = Field(default_factory=list, max_length=MAX_COORDINATION_TASKS)
    optional_dependency_task_ids: list[str] = Field(default_factory=list, max_length=MAX_COORDINATION_TASKS)
    finding_requirements: list["FindingRequirement"] = Field(default_factory=list, max_length=50)
    status: TaskExecutionStatus = "pending"
    parameters: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_parameters_and_dependencies(self):
        if len(set(self.dependency_task_ids)) != len(self.dependency_task_ids):
            raise ValueError("dependency_task_ids must be unique.")
        parameter_model = _PARAMETER_MODELS[self.domain]
        validated = parameter_model.model_validate(self.parameters)
        object.__setattr__(self, "parameters", validated.model_dump(mode="python", exclude_unset=True))
        return self


class FindingRequirement(BaseModel):
    source_task_id: str = Field(min_length=1, max_length=80)
    finding_id: str = Field(min_length=1, max_length=100)

    model_config = ConfigDict(extra="forbid", frozen=True)


CoordinationTask.model_rebuild()


class TaskExecutionContext(BaseModel):
    """Only the findings explicitly requested by one task, never identity or services."""

    findings: list["AgentFinding"] = Field(default_factory=list, max_length=200)
    unavailable_finding_ids: list[str] = Field(default_factory=list, max_length=200)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_reference_sets(self):
        finding_ids = [finding.finding_id for finding in self.findings]
        if len(set(finding_ids)) != len(finding_ids):
            raise ValueError("Execution context findings must be unique.")
        if len(set(self.unavailable_finding_ids)) != len(self.unavailable_finding_ids):
            raise ValueError("Unavailable finding IDs must be unique.")
        if set(finding_ids).intersection(self.unavailable_finding_ids):
            raise ValueError("A finding cannot be both available and unavailable.")
        return self


class TaskResult(BaseModel):
    task_id: str = Field(min_length=1, max_length=80)
    domain: CoordinationDomain
    status: TaskExecutionStatus
    result: dict[str, Any] | None = None
    safe_error_code: SafeTaskErrorCode | None = None
    duration_ms: float | None = Field(default=None, ge=0, le=86_400_000)
    attempt_count: int = Field(default=1, ge=0, le=32)
    finding_ids: list[str] = Field(default_factory=list, max_length=100)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("result")
    @classmethod
    def validate_structured_result(cls, value):
        if value is None:
            return value
        return _validate_context_value(value, field_name="Task result")

    @model_validator(mode="after")
    def validate_result_status(self):
        if self.status == "failed":
            if self.safe_error_code is None or self.result is not None:
                raise ValueError("Failed tasks require a safe error code and cannot include a result.")
        elif self.status == "skipped":
            if self.result is not None:
                raise ValueError("Skipped tasks cannot include a result.")
            if self.safe_error_code not in {
                None, "dependency_failed", "required_finding_missing", "investigation_not_warranted",
                "budget_exceeded",
            }:
                raise ValueError("Skipped tasks require a safe skip reason.")
        elif self.safe_error_code is not None:
            raise ValueError("Only failed tasks may include a safe error code.")
        if self.status == "succeeded" and self.result is None:
            raise ValueError("Succeeded tasks require a structured result.")
        if self.status in {"succeeded", "failed"} and self.attempt_count < 1:
            raise ValueError("Executed tasks require at least one attempt.")
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("finding_ids must be unique.")
        return self


class ProfitabilityComparison(BaseModel):
    """Explicit, deterministic two-period net-profit comparison evidence."""

    current_period_start: date | None
    current_period_end: date | None
    previous_period_start: date | None
    previous_period_end: date | None
    current_value: float | None = Field(default=None, allow_inf_nan=False)
    previous_value: float | None = Field(default=None, allow_inf_nan=False)
    absolute_change: float | None = Field(default=None, allow_inf_nan=False)
    percentage_change: float | None = Field(default=None, allow_inf_nan=False)
    direction: Literal["increase", "decrease", "unchanged", "unavailable"]
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    comparison_definition: str = Field(min_length=1, max_length=300)
    status: Literal["comparable", "unavailable", "incompatible"]
    unavailable_reason: Literal[
        "current_value_unavailable", "previous_value_unavailable",
        "both_values_unavailable", "periods_incompatible", "unit_mismatch",
        "source_mismatch",
    ] | None = None
    current_evidence_ref: str = Field(min_length=1, max_length=200)
    previous_evidence_ref: str = Field(min_length=1, max_length=200)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_comparison(self):
        current_dates = (self.current_period_start, self.current_period_end)
        previous_dates = (self.previous_period_start, self.previous_period_end)
        if (self.current_period_start is None) != (self.current_period_end is None):
            raise ValueError("Current comparison period requires both dates.")
        if (self.previous_period_start is None) != (self.previous_period_end is None):
            raise ValueError("Previous comparison period requires both dates.")
        for start, end in (current_dates, previous_dates):
            if start and end and start > end:
                raise ValueError("Comparison period start must not follow its end.")

        if self.status != "comparable":
            if self.unavailable_reason is None or self.direction != "unavailable":
                raise ValueError("Incomplete comparisons require a reason and unavailable direction.")
            if self.absolute_change is not None or self.percentage_change is not None:
                raise ValueError("Incomplete comparisons cannot contain calculated changes.")
            return self

        if self.unavailable_reason is not None:
            raise ValueError("Comparable findings cannot carry an unavailable reason.")
        if (not self.current_period_start or not self.previous_period_start
                or self.current_value is None or self.previous_value is None
                or self.unit is None):
            raise ValueError("Comparable findings require both periods, values, and a unit.")
        current_length = (self.current_period_end - self.current_period_start).days + 1
        previous_length = (self.previous_period_end - self.previous_period_start).days + 1
        if (current_length != previous_length
                or self.previous_period_end + timedelta(days=1) != self.current_period_start):
            raise ValueError("Comparable periods must be adjacent and equal in length.")

        current = Decimal(str(self.current_value))
        previous = Decimal(str(self.previous_value))
        delta = current - previous
        expected_delta = delta.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if self.absolute_change is None or Decimal(str(self.absolute_change)) != expected_delta:
            raise ValueError("Absolute change does not match the period values.")
        expected_direction = "increase" if delta > 0 else "decrease" if delta < 0 else "unchanged"
        if self.direction != expected_direction:
            raise ValueError("Comparison direction does not match the period values.")
        if previous == 0:
            if self.percentage_change is not None:
                raise ValueError("Percentage change is undefined from a zero previous value.")
        else:
            expected_percent = (delta / abs(previous) * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP,
            )
            if (self.percentage_change is None
                    or Decimal(str(self.percentage_change)) != expected_percent):
                raise ValueError("Percentage change does not match the period values.")
        return self

    def claim_value(self) -> dict[str, Any]:
        """Provider-visible comparison payload; internal result keys stay private."""
        return self.model_dump(mode="json", exclude={"current_evidence_ref", "previous_evidence_ref"})


class AgentFinding(BaseModel):
    finding_id: str = Field(min_length=1, max_length=100)
    domain: CoordinationDomain
    name: str = Field(min_length=1, max_length=120)
    value: Any = None
    reporting_period: ReportingPeriod | None = None
    source_service: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$")
    evidence_ref: str | None = Field(default=None, min_length=1, max_length=200)
    evidence_status: EvidenceStatus
    evidence_classification: EvidenceClassification | None = None
    data_availability: DataAvailability | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    metric_definition: str | None = Field(default=None, min_length=1, max_length=300)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    comparison: ProfitabilityComparison | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("value")
    @classmethod
    def validate_json_value(cls, value):
        return _validate_context_value(value, field_name="Finding value")

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, values):
        if any(not value.strip() or len(value) > 500 for value in values):
            raise ValueError("Limitations must be non-empty strings of at most 500 characters.")
        return values

    @model_validator(mode="after")
    def unavailable_has_no_value(self):
        if self.evidence_status == "unavailable" and self.value is not None:
            raise ValueError("Unavailable findings cannot include a value.")
        if self.evidence_classification is None:
            object.__setattr__(self, "evidence_classification", (
                "UNAVAILABLE" if self.evidence_status == "unavailable" else "CALCULATED"
            ))
        if self.data_availability is None:
            object.__setattr__(self, "data_availability", {
                "verified": "available", "estimated": "partial",
                "unavailable": "unavailable", "conflicting": "partial",
            }[self.evidence_status])
        if (self.evidence_classification == "UNAVAILABLE"
                and (self.value is not None or self.data_availability != "unavailable")):
            raise ValueError("UNAVAILABLE evidence requires a null value and unavailable data status.")
        if self.evidence_status == "unavailable" and self.evidence_classification != "UNAVAILABLE":
            raise ValueError("Unavailable findings must use UNAVAILABLE evidence classification.")
        if self.comparison is not None:
            if self.comparison.status == "comparable":
                if (self.value != self.comparison.claim_value()
                        or self.unit != self.comparison.unit
                        or self.reporting_period is None
                        or self.reporting_period.start_date != self.comparison.current_period_start
                        or self.reporting_period.end_date != self.comparison.current_period_end):
                    raise ValueError("Trend finding value and period must match its comparison evidence.")
            elif self.value is not None or self.evidence_status != "unavailable":
                raise ValueError("Incomplete comparisons must be represented as unavailable findings.")
        return self


TaskExecutionContext.model_rebuild()


class CoordinationPlan(BaseModel):
    plan_id: str = Field(min_length=1, max_length=100)
    tasks: list[CoordinationTask] = Field(max_length=MAX_COORDINATION_TASKS)
    status: PlanStatus = "draft"
    validation_errors: list[SafeTaskErrorCode] = Field(default_factory=list, max_length=20)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_task_graph(self):
        task_ids = [task.task_id for task in self.tasks]
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("Task IDs must be unique within a plan.")
        known_ids = set(task_ids)
        dependencies: dict[str, list[str]] = {}
        for task in self.tasks:
            if len(set(task.dependency_task_ids)) != len(task.dependency_task_ids):
                raise ValueError(f"Task '{task.task_id}' dependencies must be unique.")
            if len(set(task.optional_dependency_task_ids)) != len(task.optional_dependency_task_ids):
                raise ValueError(f"Task '{task.task_id}' optional dependencies must be unique.")
            if not set(task.optional_dependency_task_ids).issubset(task.dependency_task_ids):
                raise ValueError(f"Task '{task.task_id}' optional dependencies must be declared dependencies.")
            for dependency_id in task.dependency_task_ids:
                if dependency_id == task.task_id:
                    raise ValueError(f"Task '{task.task_id}' cannot depend on itself.")
                if dependency_id not in known_ids:
                    raise ValueError(f"Task '{task.task_id}' references a missing dependency.")
            dependencies[task.task_id] = task.dependency_task_ids
            requirement_ids = [requirement.finding_id for requirement in task.finding_requirements]
            if len(set(requirement_ids)) != len(requirement_ids):
                raise ValueError(f"Task '{task.task_id}' finding requirements must be unique.")
            for requirement in task.finding_requirements:
                if requirement.source_task_id not in task.dependency_task_ids:
                    raise ValueError(f"Task '{task.task_id}' finding source must be a declared dependency.")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str):
            if task_id in visiting:
                raise ValueError("Task dependencies must not contain cycles.")
            if task_id in visited:
                return
            visiting.add(task_id)
            for dependency_id in dependencies[task_id]:
                visit(dependency_id)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in task_ids:
            visit(task_id)
        task_positions = {task_id: position for position, task_id in enumerate(task_ids)}
        for task in self.tasks:
            if any(task_positions[dependency] >= task_positions[task.task_id]
                   for dependency in task.dependency_task_ids):
                raise ValueError("Tasks must be ordered after their dependencies.")
        return self


class SharedFindingsContext(BaseModel):
    """In-memory findings/results container. Identity and service objects belong elsewhere."""

    task_results: dict[str, TaskResult] = Field(default_factory=dict)
    findings: dict[str, AgentFinding] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_keys(self):
        if any(key != result.task_id for key, result in self.task_results.items()):
            raise ValueError("Task result keys must match task IDs.")
        if any(key != finding.finding_id for key, finding in self.findings.items()):
            raise ValueError("Finding keys must match finding IDs.")
        return self

    def with_task_result(self, result: TaskResult) -> "SharedFindingsContext":
        results = dict(self.task_results)
        if result.task_id in results:
            raise ValueError("Task IDs cannot be executed more than once per request.")
        results[result.task_id] = result
        return self.model_copy(update={"task_results": results})

    def with_finding(self, finding: AgentFinding) -> "SharedFindingsContext":
        findings = dict(self.findings)
        if finding.finding_id in findings:
            raise ValueError("Finding IDs cannot be duplicated within a request.")
        findings[finding.finding_id] = finding
        return self.model_copy(update={"findings": findings})
