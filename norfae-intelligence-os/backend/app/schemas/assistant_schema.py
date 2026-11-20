from datetime import date, datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


AssistantIntentName = Literal[
    "profitability", "products", "cities", "marketing", "creatives",
    "anomalies", "overview", "recommendations", "data_quality", "multi_domain", "unsupported",
]
AssistantDomain = Literal[
    "profitability", "products", "cities", "marketing", "creatives", "anomalies", "data_quality",
]
ToolExecutionStatus = Literal["success", "failed", "skipped"]


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = Field(default=None, ge=1)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AssistantConversationSummary(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class AssistantMessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class AssistantConversationDetail(AssistantConversationSummary):
    messages: list[AssistantMessageResponse]


class AssistantIntent(BaseModel):
    intent: AssistantIntentName
    start_date: date | None = None
    end_date: date | None = None
    requested_domains: list[AssistantDomain] = Field(default_factory=list, max_length=7)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date.")
        if len(set(self.requested_domains)) != len(self.requested_domains):
            raise ValueError("requested_domains must not contain duplicates.")
        return self


class GroundedRecommendation(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=5)


class AssistantClaim(BaseModel):
    """Internal factual assertion tied to exact, request-validated findings."""

    claim_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$")
    text: str = Field(min_length=1, max_length=500)
    finding_ids: list[str] = Field(min_length=1, max_length=5)
    domain: AssistantDomain
    metric_name: str = Field(min_length=1, max_length=120)
    period_start: date | None = None
    period_end: date | None = None
    claim_type: Literal["numeric", "qualitative"]
    value: Any
    unit: str | None = Field(default=None, max_length=40)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_claim_shape(self):
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("Claim finding IDs must be unique.")
        if (self.period_start is None) != (self.period_end is None):
            raise ValueError("Claim periods require both endpoints.")
        if self.period_start and self.period_start > self.period_end:
            raise ValueError("Claim period start must not follow its end.")
        return self


class AssistantRecommendationIntent(BaseModel):
    """Allowlisted request to render a recommendation from validated evidence."""

    action: Literal["review_metric", "collect_data", "compare_periods"]
    finding_ids: list[str] = Field(min_length=1, max_length=5)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_findings(self):
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("Recommendation finding IDs must be unique.")
        return self


class AssistantDraft(BaseModel):
    answer: str = Field(min_length=1, max_length=3000)
    answer_evidence_ids: list[str] = Field(default_factory=list, max_length=8)
    interpretation: str = Field(default="", max_length=1500)
    recommendations: list[GroundedRecommendation] = Field(default_factory=list, max_length=5)
    unknowns: list[str] = Field(default_factory=list, max_length=10)
    claims: list[AssistantClaim] = Field(default_factory=list, max_length=12)
    recommendation_intents: list[AssistantRecommendationIntent] = Field(default_factory=list, max_length=5)

    model_config = ConfigDict(extra="forbid")


class AssistantExecutionSummary(BaseModel):
    execution_id: str
    status: Literal["complete", "partial", "failed", "unsupported"]
    nodes_executed: list[str]
    tools: dict[str, ToolExecutionStatus]
    errors: list[str]


class AssistantChatResponse(BaseModel):
    conversation_id: int
    intent: AssistantIntentName
    answer: str
    answer_evidence_ids: list[str]
    verified_facts: dict[str, object]
    interpretation: str
    recommendations: list[GroundedRecommendation]
    unknowns: list[str]
    limitations: list[str]
    execution: AssistantExecutionSummary


class AssistantDeleteResponse(BaseModel):
    deleted: bool
