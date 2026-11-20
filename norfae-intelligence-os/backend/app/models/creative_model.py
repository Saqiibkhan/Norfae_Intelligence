from sqlalchemy import Column, ForeignKey, Integer, String, Float, DateTime
from datetime import datetime

from app.core.database import Base


class Creative(Base):
    __tablename__ = "creatives"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)

    creative_name = Column(String, nullable=False)

    platform = Column(String, nullable=True)

    spend = Column(Float, default=0)

    revenue = Column(Float, default=0)

    roas = Column(Float, default=0)

    ctr = Column(Float, default=0)

    cpc = Column(Float, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
