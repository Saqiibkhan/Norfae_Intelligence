from typing import Any

from pydantic import BaseModel, ConfigDict

from app.agents.base import BaseAgent
from app.agents.context import AgentContext
from app.schemas.intelligence_schema import DataQualityReport
from app.services.data_quality_service import DataQualityService


class DataAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DataAnalysisAgent(BaseAgent[DataAnalysisInput, DataQualityReport]):
    agent_id = "data_analysis"
    name = "Data Analysis Agent"
    description = "Read-only validation and quality reporting for tenant business records."
    input_schema = DataAnalysisInput
    output_schema = DataQualityReport
    required_permission = "analytics:read"

    async def run(self, payload: DataAnalysisInput, context: AgentContext) -> Any:
        business_id = int(context.require_business_scope(self.required_permission))
        db = context.get_business_dependency("db", self.required_permission)
        return DataQualityService.analyze(db, business_id)
