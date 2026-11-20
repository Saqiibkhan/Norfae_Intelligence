from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ShopifyStatusResponse(BaseModel):
    service: Literal["shopify"]
    initialized: bool
    connected: bool
    store: str | None
    message: str


class ShopifySyncRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: int
    sync_type: Literal["products", "orders", "full"]
    trigger_type: Literal["manual"]
    status: Literal["running", "completed", "partially_completed", "failed"]
    records_fetched: int
    records_created: int
    records_updated: int
    records_skipped: int
    error_category: str | None = None
    message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class ShopifyFullSyncResponse(BaseModel):
    status: Literal["completed", "partially_completed", "failed"]
    run: ShopifySyncRunResponse
    products: ShopifySyncRunResponse
    orders: ShopifySyncRunResponse
