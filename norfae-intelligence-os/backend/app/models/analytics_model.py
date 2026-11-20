from sqlalchemy import Column, ForeignKey, Integer, Float, DateTime
from datetime import datetime

from app.core.database import Base


class Analytics(Base):
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)

    total_orders = Column(Integer, default=0)

    total_revenue = Column(Float, default=0)

    total_spend = Column(Float, default=0)

    total_profit = Column(Float, default=0)

    average_roas = Column(Float, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
