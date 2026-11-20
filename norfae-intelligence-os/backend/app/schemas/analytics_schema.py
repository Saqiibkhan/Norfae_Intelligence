from pydantic import BaseModel


class AnalyticsResponse(BaseModel):
    total_orders: int
    total_revenue: float
    total_expenses: float
    total_profit: float
    profit_margin: float