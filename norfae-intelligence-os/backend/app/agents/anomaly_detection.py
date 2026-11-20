from typing import Any

from starlette.concurrency import run_in_threadpool

from app.agents.base import BaseAgent
from app.agents.context import AgentContext
from app.schemas.anomaly_schema import AnomalyQuery, AnomalyReport
from app.services.anomaly_detection_service import AnomalyDetectionService


class AnomalyDetectionAgent(BaseAgent[AnomalyQuery, AnomalyReport]):
    agent_id = "anomaly_detection"
    name = "Anomaly Detection Agent"
    description = "Explainable, read-only statistical anomaly detection over business-scoped data."
    input_schema = AnomalyQuery
    output_schema = AnomalyReport
    required_permission = "analytics:read"

    async def run(self, payload: AnomalyQuery, context: AgentContext) -> Any:
        business_id = int(context.require_business_scope(self.required_permission))
        db = context.get_business_dependency("db", self.required_permission)
        service = context.get_dependency("anomaly_detection_service")
        return await run_in_threadpool(service.list_anomalies, db, business_id, payload)
