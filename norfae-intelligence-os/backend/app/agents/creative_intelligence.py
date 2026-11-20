from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool

from app.agents.base import BaseAgent
from app.agents.context import AgentContext
from app.schemas.creative_schema import CreativeIntelligencePage
from app.services.creative_intelligence_service import CreativeIntelligenceService


class CreativeIntelligenceInput(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_period(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date.")
        return self


class CreativeIntelligenceAgent(BaseAgent[CreativeIntelligenceInput, CreativeIntelligencePage]):
    agent_id = "creative_intelligence"
    name = "Creative Intelligence Agent"
    description = "Read-only analysis of legacy recorded creative metrics with source limitations."
    input_schema = CreativeIntelligenceInput
    output_schema = CreativeIntelligencePage
    required_permission = "analytics:read"

    async def run(self, payload: CreativeIntelligenceInput, context: AgentContext) -> Any:
        business_id = int(context.require_business_scope(self.required_permission))
        db = context.get_business_dependency("db", self.required_permission)
        return await run_in_threadpool(
            CreativeIntelligenceService.list_creatives,
            db, business_id, payload.start_date, payload.end_date,
            payload.page, payload.page_size,
        )
