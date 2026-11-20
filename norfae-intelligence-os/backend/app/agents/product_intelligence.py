from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agents.base import BaseAgent
from app.agents.context import AgentContext
from app.schemas.intelligence_schema import ProductIntelligencePage
from app.services.product_intelligence_service import ProductIntelligenceService


class ProductIntelligenceInput(BaseModel):
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


class ProductIntelligenceAgent(BaseAgent[ProductIntelligenceInput, ProductIntelligencePage]):
    agent_id = "product_intelligence"
    name = "Product Intelligence Agent"
    description = "Deterministic, tenant-scoped product performance and contribution analysis."
    input_schema = ProductIntelligenceInput
    output_schema = ProductIntelligencePage
    required_permission = "analytics:read"

    async def run(self, payload: ProductIntelligenceInput, context: AgentContext) -> Any:
        business_id = int(context.require_business_scope(self.required_permission))
        db = context.get_business_dependency("db", self.required_permission)
        return ProductIntelligenceService.analyze_business(
            db, business_id, payload.start_date, payload.end_date,
            payload.page, payload.page_size,
        )
