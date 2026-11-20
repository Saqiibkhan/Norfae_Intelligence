from sqlalchemy import Column, ForeignKey, Integer, String, DateTime
from datetime import datetime

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    # Null business_id is reserved for system-wide audit events.
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True, index=True)

    action = Column(String, nullable=False)

    performed_by = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
