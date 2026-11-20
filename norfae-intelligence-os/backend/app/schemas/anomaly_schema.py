from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


AnomalyCategory = Literal[
    "sales", "profitability", "marketing", "operations", "cost"
]
AnomalySeverity = Literal["medium", "high"]


class AnomalyQuery(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    category: AnomalyCategory | None = None
    severity: AnomalySeverity | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_period(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date.")
        return self


class AnomalyRecord(BaseModel):
    anomaly_id: str
    business_id: int
    category: AnomalyCategory
    severity: AnomalySeverity
    metric_name: str
    observed_value: float
    expected_value: float | None
    deviation_value: float | None
    deviation_percent: float | None
    detection_method: str
    period_start: date
    period_end: date
    explanation: str
    recommended_investigation: str


class AnomalyReport(BaseModel):
    business_id: int
    start_date: date
    end_date: date
    total: int
    page: int
    page_size: int
    anomalies: list[AnomalyRecord]
    insufficient_data: list[str]
    warnings: list[str]


class AnomalySummary(BaseModel):
    business_id: int
    start_date: date
    end_date: date
    total: int
    by_category: dict[str, int]
    by_severity: dict[str, int]
    insufficient_data: list[str]
    warnings: list[str]
