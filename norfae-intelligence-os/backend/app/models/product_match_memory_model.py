from sqlalchemy import Column, ForeignKey, Integer, String, Float, DateTime

from datetime import datetime

from app.core.database import Base


class ProductMatchMemory(Base):

    __tablename__ = "product_match_memory"

    # ===================================
    # PRIMARY
    # ===================================

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)

    # ===================================
    # RAW ORDER DATA
    # ===================================

    raw_product_name = Column(String, index=True)

    # ===================================
    # NORMALIZED MATCHING
    # ===================================

    normalized_name = Column(String, index=True)

    normalized_size = Column(String, index=True, nullable=True)

    # ===================================
    # ORIGINAL ORDER VALUES
    # ===================================

    raw_size = Column(String, nullable=True)

    raw_price = Column(Float, nullable=True)

    # ===================================
    # MATCHED PRODUCT
    # ===================================

    matched_sku = Column(String, index=True)

    matched_product_name = Column(String)

    confidence_score = Column(Float, default=0)

    # ===================================
    # TIMESTAMPS
    # ===================================

    created_at = Column(DateTime, default=datetime.utcnow)
