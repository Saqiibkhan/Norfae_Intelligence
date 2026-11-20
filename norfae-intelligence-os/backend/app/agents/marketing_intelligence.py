from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool

from app.agents.base import BaseAgent
from app.agents.context import AgentContext
from app.schemas.intelligence_schema import (
    MarketingCampaignPage,
    MarketingOverview,
    MarketingTrendResponse,
)
from app.services.marketing_intelligence_service import MarketingIntelligenceService


class MarketingInput(BaseModel):
    start_date: date | None = None
    end_date: date | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_period(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date.")
        return self


class MarketingCampaignInput(MarketingInput):
    level: Literal["campaign", "adset", "ad"] = "campaign"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class MarketingOverviewAgent(BaseAgent[MarketingInput, MarketingOverview]):
    agent_id = "marketing_overview"
    name = "Marketing Overview Agent"
    description = "Read-only account-level Meta marketing metrics with explicit attribution limits."
    input_schema = MarketingInput
    output_schema = MarketingOverview
    required_permission = "analytics:read"

    async def run(self, payload: MarketingInput, context: AgentContext) -> Any:
        business_id = int(context.require_business_scope(self.required_permission))
        db = context.get_business_dependency("db", self.required_permission)
        return await run_in_threadpool(
            MarketingIntelligenceService.overview,
            db, business_id, payload.start_date, payload.end_date,
        )


class MarketingCampaignAgent(BaseAgent[MarketingCampaignInput, MarketingCampaignPage]):
    agent_id = "marketing_campaigns"
    name = "Marketing Campaign Agent"
    description = "Read-only campaign, ad-set, and ad analysis from Meta-reported insights."
    input_schema = MarketingCampaignInput
    output_schema = MarketingCampaignPage
    required_permission = "analytics:read"

    async def run(self, payload: MarketingCampaignInput, context: AgentContext) -> Any:
        business_id = int(context.require_business_scope(self.required_permission))
        db = context.get_business_dependency("db", self.required_permission)
        return await run_in_threadpool(
            lambda: MarketingIntelligenceService.campaigns(
                db, business_id, payload.start_date, payload.end_date,
                level=payload.level, page=payload.page, page_size=payload.page_size,
            )
        )


class MarketingTrendsAgent(BaseAgent[MarketingInput, MarketingTrendResponse]):
    agent_id = "marketing_trends"
    name = "Marketing Trends Agent"
    description = "Read-only daily spend and traffic trends from stored Meta statistics."
    input_schema = MarketingInput
    output_schema = MarketingTrendResponse
    required_permission = "analytics:read"

    async def run(self, payload: MarketingInput, context: AgentContext) -> Any:
        business_id = int(context.require_business_scope(self.required_permission))
        db = context.get_business_dependency("db", self.required_permission)
        return await run_in_threadpool(
            MarketingIntelligenceService.trends,
            db, business_id, payload.start_date, payload.end_date,
        )
