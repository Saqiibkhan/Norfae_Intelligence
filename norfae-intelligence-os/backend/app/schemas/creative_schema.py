from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Literal


class CreativeBase(BaseModel):
    creative_name: str
    platform: str
    ctr: float
    roas: float
    spend: float


class CreativeCreate(CreativeBase):
    pass


class CreativeResponse(CreativeBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class CreativeRecordedMetric(BaseModel):
    amount: float | None
    available: bool
    note: str


class CreativeIntelligenceItem(BaseModel):
    creative_id: int
    creative_name: str
    platform: str | None
    created_at: datetime | None
    creative_type: str | None
    campaign_id: str | None
    campaign_name: str | None
    ad_id: str | None
    ad_name: str | None
    spend: CreativeRecordedMetric
    revenue: CreativeRecordedMetric
    recorded_roas: CreativeRecordedMetric
    recorded_ctr: CreativeRecordedMetric
    recorded_cpc: CreativeRecordedMetric
    impressions: float | None
    reach: float | None
    clicks: float | None
    frequency: float | None
    reported_conversions: float | None
    conversion_value: float | None
    source: Literal["legacy creatives table"]


class CreativeIntelligencePage(BaseModel):
    business_id: int
    start_date: date | None
    end_date: date | None
    total: int
    page: int
    page_size: int
    best_recorded_roas_creative_id: int | None
    lowest_recorded_roas_creative_id: int | None
    creatives: list[CreativeIntelligenceItem]
    warnings: list[str]


class CreativeComparison(BaseModel):
    business_id: int
    requested_creative_ids: list[int]
    creatives: list[CreativeIntelligenceItem]
    missing_creative_ids: list[int]
    warning: str


class VisualAssetAnalysis(BaseModel):
    status: Literal["analyzed", "unavailable", "unsupported", "failed"]
    media_kind: Literal["image", "video"]
    width: int | None
    height: int | None
    aspect_ratio: float | None
    dominant_colors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
