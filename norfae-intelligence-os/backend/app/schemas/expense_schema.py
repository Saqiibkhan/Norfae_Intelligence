from pydantic import BaseModel

from datetime import datetime

from typing import Optional


class ExpenseBase(BaseModel):

    title: str

    amount: float

    category: Optional[str] = None

    payment_method: Optional[str] = None

    notes: Optional[str] = None

    is_recurring: bool = False

    recurring_cycle: Optional[str] = None

    source: Optional[str] = "manual"


class ExpenseCreate(ExpenseBase):

    created_at: Optional[datetime] = None


class ExpenseResponse(ExpenseBase):

    id: int

    created_at: datetime

    external_reference: Optional[str] = None

    expense_date: Optional[datetime] = None

    class Config:

        from_attributes = True
