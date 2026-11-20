from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MetaSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_range(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date.")
        if (self.end_date - self.start_date).days > 91:
            raise ValueError("A Meta sync may cover no more than 92 calendar days.")
        return self


class MetaAccount(BaseModel):
    id: str
    name: str | None = None
    account_status: int | None = None
    currency: str | None = None
    timezone_name: str | None = None


class MetaStatusResponse(BaseModel):
    configured: bool
    selected_account_id: str | None
    connected: bool
    last_synced_at: datetime | None = None
    message: str


class MetaSyncRunResponse(BaseModel):
    run_id: int
    account_id: str
    start_date: date
    end_date: date
    status: str
    records_fetched: int
    records_created: int
    records_updated: int
    records_skipped: int
    error_category: str | None = None
    message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class MetaSyncResponse(BaseModel):
    status: str
    run: MetaSyncRunResponse


class MetaHistoryEntry(MetaSyncRunResponse):
    pass


class MetaAccountsResponse(BaseModel):
    accounts: list[MetaAccount] = Field(default_factory=list)
