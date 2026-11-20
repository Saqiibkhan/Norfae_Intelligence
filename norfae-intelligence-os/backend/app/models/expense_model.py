from sqlalchemy import Column, ForeignKey, Integer, String, Float, Boolean, DateTime, UniqueConstraint

from datetime import datetime

from app.core.database import Base

from app.core.timezone import pakistan_now


class Expense(Base):

    __tablename__ = "expenses"
    __table_args__ = (UniqueConstraint("business_id", "external_reference", name="uq_expenses_business_external_reference"),)

    # ===================================
    # PRIMARY
    # ===================================

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)

    # ===================================
    # CORE
    # ===================================

    title = Column(String, nullable=False)

    amount = Column(Float, default=0)

    category = Column(String, nullable=True)

    # ===================================
    # ADVANCED FINANCIALS
    # ===================================

    payment_method = Column(String, nullable=True)

    notes = Column(String, nullable=True)

    # ===================================
    # RECURRING ENGINE
    # ===================================

    is_recurring = Column(Boolean, default=False)

    recurring_cycle = Column(String, nullable=True)

    # ===================================
    # SOURCE TRACKING
    # ===================================

    source = Column(String, nullable=True)

    external_reference = Column(
        String,
        nullable=True,
    )

    expense_date = Column(DateTime, nullable=True)

    # ===================================
    # TIMESTAMPS
    # ===================================

    created_at = Column(
        DateTime,
        default=pakistan_now,
    )
