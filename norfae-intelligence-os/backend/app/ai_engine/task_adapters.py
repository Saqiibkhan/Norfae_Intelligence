"""Fixed, typed adapters between coordination tasks and deterministic services."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Any, Generic, Literal, TypeVar
from typing import get_args

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.exc import OperationalError
from starlette.concurrency import run_in_threadpool

from app.agents.context import AgentContext
from app.agents.errors import AgentError, AgentPermissionError
from app.agents.city_intelligence import CityIntelligenceInput
from app.agents.creative_intelligence import CreativeIntelligenceInput
from app.agents.data_analysis import DataAnalysisInput
from app.agents.marketing_intelligence import MarketingInput
from app.agents.product_intelligence import ProductIntelligenceInput
from app.schemas.anomaly_schema import AnomalyQuery, AnomalyReport, AnomalySummary
from app.schemas.assistant_schema import AssistantDomain
from app.schemas.coordination_schema import (
    CoordinationTask,
    ProfitabilityTaskParameters,
    TaskExecutionContext,
)
from app.schemas.creative_schema import CreativeIntelligencePage
from app.schemas.intelligence_schema import (
    CityIntelligencePage,
    DataQualityReport,
    MarketingOverview,
    MarketingTrendResponse,
    ProductIntelligencePage,
    ProductProfitability,
    ProfitabilitySummary,
)
from app.services.city_intelligence_service import CityIntelligenceService
from app.services.creative_intelligence_service import CreativeIntelligenceService
from app.services.data_quality_service import DataQualityService
from app.services.deterministic_profitability_service import DeterministicProfitabilityService
from app.services.marketing_intelligence_service import MarketingIntelligenceService
from app.services.product_intelligence_service import ProductIntelligenceService
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.tenant_context import tenant_scope

logger = logging.getLogger("norfae_os.assistant.adapters")

AdapterErrorCategory = Literal[
    "INVALID_TASK", "UNSUPPORTED_DOMAIN", "PERMISSION_DENIED", "DATA_UNAVAILABLE",
    "VALIDATION_ERROR", "TRANSIENT_FAILURE", "TIMEOUT", "BUDGET_EXCEEDED", "INTERNAL_ERROR",
]


class TaskAdapterError(Exception):
    """Safe adapter failure with a stable category and no raw underlying details."""

    def __init__(self, category: AdapterErrorCategory):
        self.category = category
        super().__init__(f"Task adapter failed safely ({category}).")


async def _join_worker_without_abandoning(worker: asyncio.Task):
    """Wait until a thread-pool worker has released its owned resources.

    asyncio cancellation cannot stop a Python thread. Repeated cancellation requests
    are temporarily consumed while the worker is joined, then reported to the caller.
    """
    caller = asyncio.current_task()
    cancelled_during_join = False
    while not worker.done():
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError:
            if worker.done():
                break
            cancelled_during_join = True
            if caller is not None:
                while caller.cancelling():
                    caller.uncancel()
        except BaseException:
            break

    try:
        result = worker.result()
        worker_error = None
    except BaseException as error:
        result = None
        worker_error = error
    return result, worker_error, cancelled_during_join


class DuplicateTaskAdapterError(ValueError):
    pass


class ProfitabilityTaskOutput(BaseModel):
    profitability: ProfitabilitySummary
    previous_period_profitability: ProfitabilitySummary
    product_profitability: list[ProductProfitability]

    model_config = ConfigDict(extra="forbid")


class MarketingTaskOutput(BaseModel):
    marketing_overview: MarketingOverview
    marketing_trends: MarketingTrendResponse

    model_config = ConfigDict(extra="forbid")


class AnomalyTaskOutput(BaseModel):
    anomalies: AnomalySummary
    anomaly_records: AnomalyReport

    model_config = ConfigDict(extra="forbid")


class ProductTaskOutput(BaseModel):
    products: ProductIntelligencePage

    model_config = ConfigDict(extra="forbid")


class CityTaskOutput(BaseModel):
    cities: CityIntelligencePage

    model_config = ConfigDict(extra="forbid")


class CreativeTaskOutput(BaseModel):
    creatives: CreativeIntelligencePage

    model_config = ConfigDict(extra="forbid")


class DataQualityTaskOutput(BaseModel):
    data_quality: DataQualityReport

    model_config = ConfigDict(extra="forbid")


ParametersT = TypeVar("ParametersT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class TaskAdapter(ABC, Generic[ParametersT, OutputT]):
    domain: AssistantDomain
    parameters_schema: type[ParametersT]
    output_schema: type[OutputT]

    async def execute(
        self,
        task: CoordinationTask,
        context: AgentContext,
        execution_context: TaskExecutionContext | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> OutputT:
        try:
            if not isinstance(task, CoordinationTask):
                task = CoordinationTask.model_validate(task)
            execution_context = TaskExecutionContext.model_validate(execution_context or {})
        except ValidationError:
            raise TaskAdapterError("INVALID_TASK") from None
        if task.domain != self.domain:
            raise TaskAdapterError("INVALID_TASK")
        requirements = {requirement.finding_id: requirement for requirement in task.finding_requirements}
        provided_findings = {finding.finding_id: finding for finding in execution_context.findings}
        unavailable_ids = set(execution_context.unavailable_finding_ids)
        if set(provided_findings).union(unavailable_ids) != set(requirements):
            raise TaskAdapterError("INVALID_TASK")
        for finding_id in requirements:
            finding = provided_findings.get(finding_id)
            if finding is not None and finding.evidence_status in {"unavailable", "conflicting"}:
                raise TaskAdapterError("INVALID_TASK")
        try:
            parameters = self.parameters_schema.model_validate(task.parameters)
        except ValidationError:
            raise TaskAdapterError("VALIDATION_ERROR") from None

        if not context.user_id:
            raise TaskAdapterError("PERMISSION_DENIED")
        try:
            business_id = int(context.require_business_scope("analytics:read"))
        except (AgentPermissionError, TypeError, ValueError):
            raise TaskAdapterError("PERMISSION_DENIED") from None
        try:
            request_db = context.get_business_dependency("db", "analytics:read")
            bind = request_db.get_bind()
        except AgentError:
            raise TaskAdapterError("DATA_UNAVAILABLE") from None
        except Exception:
            raise TaskAdapterError("DATA_UNAVAILABLE") from None
        approved_dependencies = self.approved_dependencies(context)

        timeout = min(
            settings.ASSISTANT_TASK_TIMEOUT_SECONDS
            if timeout_seconds is None else max(0.0, timeout_seconds),
            settings.ASSISTANT_TASK_TIMEOUT_SECONDS,
        )
        worker = asyncio.create_task(run_in_threadpool(
            self._run_with_owned_session,
            bind,
            business_id,
            parameters,
            approved_dependencies,
            execution_context,
        ))
        try:
            done, _ = await asyncio.wait({worker}, timeout=timeout)
            if not done:
                # The worker owns its Session. No cross-thread driver cancellation is
                # attempted; join it before reporting timeout or releasing request resources.
                _, _, cancelled = await _join_worker_without_abandoning(worker)
                if cancelled:
                    raise asyncio.CancelledError
                raise TaskAdapterError("TIMEOUT") from None
            raw_result = worker.result()
        except asyncio.CancelledError:
            await _join_worker_without_abandoning(worker)
            raise
        except TaskAdapterError:
            raise
        except (TimeoutError, OperationalError):
            logger.warning("Intelligence task encountered a transient service failure", extra={"domain": self.domain})
            raise TaskAdapterError("TRANSIENT_FAILURE") from None
        except ValueError:
            raise TaskAdapterError("VALIDATION_ERROR") from None
        except Exception as error:
            logger.error(
                "Intelligence task failed",
                extra={"domain": self.domain, "error_type": type(error).__name__},
            )
            raise TaskAdapterError("INTERNAL_ERROR") from None

        try:
            if isinstance(raw_result, BaseModel):
                raw_result = raw_result.model_dump(mode="python")
            return self.output_schema.model_validate(raw_result)
        except (ValidationError, TypeError, ValueError):
            logger.error("Intelligence task returned an invalid output", extra={"domain": self.domain})
            raise TaskAdapterError("VALIDATION_ERROR") from None

    def _run_with_owned_session(
        self, bind, business_id, parameters, dependencies, execution_context,
    ):
        """Open, use, roll back, and close a tenant session wholly in its worker thread."""
        with tenant_scope(business_id):
            db = SessionLocal(bind=bind)
            try:
                return self.run_sync(
                    db, business_id, parameters, dependencies, execution_context,
                )
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()

    def approved_dependencies(self, context: AgentContext) -> dict[str, Any]:
        return {}

    @abstractmethod
    def run_sync(
        self,
        db: Any,
        business_id: int,
        parameters: ParametersT,
        dependencies: dict[str, Any],
        execution_context: TaskExecutionContext,
    ) -> OutputT:
        """Call a fixed deterministic service using the validated tenant scope."""


class ProfitabilityTaskAdapter(TaskAdapter[ProfitabilityTaskParameters, ProfitabilityTaskOutput]):
    domain = "profitability"
    parameters_schema = ProfitabilityTaskParameters
    output_schema = ProfitabilityTaskOutput

    def run_sync(self, db, business_id, parameters, dependencies, execution_context):
        end_date = parameters.end_date or date.today()
        start_date = parameters.start_date or (end_date - timedelta(days=29))
        if start_date > end_date:
            raise ValueError("Invalid profitability task period.")
        current = DeterministicProfitabilityService.overall(db, business_id, start_date, end_date)
        duration = (end_date - start_date).days + 1
        previous_end = start_date - timedelta(days=1)
        previous_start = previous_end - timedelta(days=duration - 1)
        previous = DeterministicProfitabilityService.overall(db, business_id, previous_start, previous_end)
        products = DeterministicProfitabilityService.products(db, business_id, start_date, end_date)[:20]
        return ProfitabilityTaskOutput(
            profitability=current,
            previous_period_profitability=previous,
            product_profitability=products,
        )


class ProductTaskAdapter(TaskAdapter[ProductIntelligenceInput, ProductTaskOutput]):
    domain = "products"
    parameters_schema = ProductIntelligenceInput
    output_schema = ProductTaskOutput

    def run_sync(self, db, business_id, parameters, dependencies, execution_context):
        return ProductTaskOutput(products=ProductIntelligenceService.analyze_business(
            db, business_id, parameters.start_date, parameters.end_date,
            page=parameters.page, page_size=parameters.page_size,
        ))


class CityTaskAdapter(TaskAdapter[CityIntelligenceInput, CityTaskOutput]):
    domain = "cities"
    parameters_schema = CityIntelligenceInput
    output_schema = CityTaskOutput

    def run_sync(self, db, business_id, parameters, dependencies, execution_context):
        return CityTaskOutput(cities=CityIntelligenceService.analyze_business(
            db, business_id, parameters.start_date, parameters.end_date,
        ))


class MarketingTaskAdapter(TaskAdapter[MarketingInput, MarketingTaskOutput]):
    domain = "marketing"
    parameters_schema = MarketingInput
    output_schema = MarketingTaskOutput

    def run_sync(self, db, business_id, parameters, dependencies, execution_context):
        return MarketingTaskOutput(
            marketing_overview=MarketingIntelligenceService.overview(
                db, business_id, parameters.start_date, parameters.end_date,
            ),
            marketing_trends=MarketingIntelligenceService.trends(
                db, business_id, parameters.start_date, parameters.end_date,
            ),
        )


class CreativeTaskAdapter(TaskAdapter[CreativeIntelligenceInput, CreativeTaskOutput]):
    domain = "creatives"
    parameters_schema = CreativeIntelligenceInput
    output_schema = CreativeTaskOutput

    def run_sync(self, db, business_id, parameters, dependencies, execution_context):
        return CreativeTaskOutput(creatives=CreativeIntelligenceService.list_creatives(
            db, business_id, parameters.start_date, parameters.end_date,
            parameters.page, parameters.page_size,
        ))


class AnomalyTaskAdapter(TaskAdapter[AnomalyQuery, AnomalyTaskOutput]):
    domain = "anomalies"
    parameters_schema = AnomalyQuery
    output_schema = AnomalyTaskOutput

    def approved_dependencies(self, context):
        try:
            service = context.get_business_dependency("anomaly_detection_service", "analytics:read")
        except AgentError:
            raise TaskAdapterError("DATA_UNAVAILABLE") from None
        return {"anomaly_detection_service": service}

    def run_sync(self, db, business_id, parameters, dependencies, execution_context):
        service = dependencies["anomaly_detection_service"]
        report, summary = service.detect(db, business_id, parameters)
        return AnomalyTaskOutput(anomalies=summary, anomaly_records=report)


class DataQualityTaskAdapter(TaskAdapter[DataAnalysisInput, DataQualityTaskOutput]):
    domain = "data_quality"
    parameters_schema = DataAnalysisInput
    output_schema = DataQualityTaskOutput

    def run_sync(self, db, business_id, parameters, dependencies, execution_context):
        return DataQualityTaskOutput(data_quality=DataQualityService.analyze(db, business_id))


class TaskAdapterRegistry:
    """Explicit mapping from approved domain names to fixed adapter instances."""

    def __init__(self, adapters: list[TaskAdapter] | None = None):
        self._adapters: dict[str, TaskAdapter] = {}
        for adapter in adapters if adapters is not None else self.default_adapters():
            self.register(adapter)

    @staticmethod
    def default_adapters() -> list[TaskAdapter]:
        return [
            ProfitabilityTaskAdapter(), ProductTaskAdapter(), CityTaskAdapter(),
            MarketingTaskAdapter(), CreativeTaskAdapter(), AnomalyTaskAdapter(),
            DataQualityTaskAdapter(),
        ]

    def register(self, adapter: TaskAdapter) -> None:
        if not isinstance(adapter, TaskAdapter) or adapter.domain not in get_args(AssistantDomain):
            raise TaskAdapterError("INVALID_TASK")
        if adapter.domain in self._adapters:
            raise DuplicateTaskAdapterError("An adapter is already registered for this domain.")
        self._adapters[adapter.domain] = adapter

    @property
    def domains(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def get_adapter(self, domain: str) -> TaskAdapter:
        if domain not in self._adapters:
            raise TaskAdapterError("UNSUPPORTED_DOMAIN")
        return self._adapters[domain]

    async def execute(
        self,
        task: CoordinationTask,
        context: AgentContext,
        execution_context: TaskExecutionContext | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> BaseModel:
        if not isinstance(task, CoordinationTask):
            try:
                task = CoordinationTask.model_validate(task)
            except ValidationError:
                raise TaskAdapterError("INVALID_TASK") from None
        return await self.get_adapter(task.domain).execute(
            task, context, execution_context, timeout_seconds=timeout_seconds,
        )
