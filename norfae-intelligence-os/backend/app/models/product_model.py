from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)

from datetime import datetime

from app.core.database import (
    Base
)


class Product(Base):

    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("business_id", "sku", name="uq_products_business_sku"),)

    # ===================================
    # PRIMARY
    # ===================================

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)

    # ===================================
    # PRODUCT INFO
    # ===================================

    name = Column(
        String,
        nullable=False
    )

    sku = Column(
        String,
        index=True
    )

    category = Column(
        String
    )

    # ===================================
    # VARIANT INTELLIGENCE
    # ===================================

    size = Column(
        String
    )

    website_size = Column(
        String
    )

    weight_kg = Column(
        Float,
        default=0.5
    )

    # ===================================
    # FINANCIALS
    # ===================================

    buying_price = Column(
        Float,
        default=0
    )

    selling_price = Column(
        Float,
        default=0
    )

    stock = Column(
        Integer,
        default=0
    )

    # ===================================
    # PERFORMANCE
    # ===================================

    total_orders = Column(
        Integer,
        default=0
    )

    delivered_orders = Column(
        Integer,
        default=0
    )

    cancelled_orders = Column(
        Integer,
        default=0
    )

    returned_orders = Column(
        Integer,
        default=0
    )

    # ===================================
    # AI INTELLIGENCE
    # ===================================

    health_score = Column(
        Float,
        default=100
    )

    scaling_score = Column(
        Float,
        default=0
    )

    fatigue_score = Column(
        Float,
        default=0
    )

    # ===================================
    # TIMESTAMPS
    # ===================================

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
