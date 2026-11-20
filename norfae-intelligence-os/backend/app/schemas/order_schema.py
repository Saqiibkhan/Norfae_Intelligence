from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class OrderBase(BaseModel):

    order_number: str

    customer_name: Optional[str] = None

    city: Optional[str] = None

    province: Optional[str] = None

    financial_status: Optional[str] = None

    fulfillment_status: Optional[str] = None

    total_price: float = 0

    shipping_cost: float = 0

    packaging_cost: float = 50

    gst_amount: float = 0

    fuel_surcharge: float = 0

    income_tax: float = 0

    net_profit: float = 0


class OrderCreate(OrderBase):
    pass


class OrderResponse(OrderBase):

    id: int

    created_at: datetime

    class Config:
        from_attributes = True