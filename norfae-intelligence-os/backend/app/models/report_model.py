from sqlalchemy import Column, ForeignKey, Integer, String, DateTime
from datetime import datetime

from app.core.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)

    report_name = Column(String, nullable=False)

    report_type = Column(String, nullable=True)

    generated_by = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
