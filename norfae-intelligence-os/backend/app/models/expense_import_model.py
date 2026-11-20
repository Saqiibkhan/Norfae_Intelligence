from datetime import datetime, timedelta

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Index

from app.core.database import Base


class ExpenseImport(Base):
    """Short-lived validated previews that become durable import history on confirm."""

    __tablename__ = "expense_imports"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="preview")
    fingerprint = Column(String(64), nullable=False)
    filename = Column(String(255), nullable=False)
    mapping_json = Column(Text, nullable=False)
    summary_json = Column(Text, nullable=False)
    rows_json = Column(Text, nullable=False)
    total_rows = Column(Integer, nullable=False)
    imported_rows = Column(Integer, nullable=False, default=0)
    invalid_rows = Column(Integer, nullable=False, default=0)
    duplicate_rows = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(hours=1))
    imported_at = Column(DateTime, nullable=True)


Index("ix_expense_imports_business_user_created", ExpenseImport.business_id, ExpenseImport.user_id, ExpenseImport.created_at)
