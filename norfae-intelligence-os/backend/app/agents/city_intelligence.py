from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from app.agents.base import BaseAgent
from app.agents.context import AgentContext
from app.schemas.intelligence_schema import CityIntelligencePage
from app.services.city_intelligence_service import CityIntelligenceService


class CityIntelligenceInput(BaseModel):
    start_date: date | None = None
    end_date: date | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_period(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date.")
        return self


class CityIntelligenceAgent(BaseAgent[CityIntelligenceInput, CityIntelligencePage]):
    agent_id = "city_intelligence"
    name = "City Intelligence Agent"
    description = "Deterministic, tenant-scoped city performance analysis."
    input_schema = CityIntelligenceInput
    output_schema = CityIntelligencePage
    required_permission = "analytics:read"

    async def run(self, payload: CityIntelligenceInput, context: AgentContext) -> Any:
        business_id = int(context.require_business_scope(self.required_permission))
        db = context.get_business_dependency("db", self.required_permission)
        return CityIntelligenceService.analyze_business(
            db, business_id, payload.start_date, payload.end_date
        )
