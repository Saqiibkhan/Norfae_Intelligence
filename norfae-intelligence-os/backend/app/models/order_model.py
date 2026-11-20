from sqlalchemy.orm import relationship

from sqlalchemy import Column, ForeignKey, Integer, String, Float, DateTime, Index, UniqueConstraint

from datetime import datetime

from app.core.database import Base


class Order(Base):

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("business_id", "id", name="uq_orders_business_id_id"),
        UniqueConstraint("business_id", "internal_order_id", name="uq_orders_business_internal_id"),
        UniqueConstraint("business_id", "shopify_order_id", name="uq_orders_business_shopify_order"),
    )

    # ===================================
    # PRIMARY
    # ===================================

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)

    # ===================================
    # ORDER IDS
    # ===================================

    internal_order_id = Column(String, index=True)

    shopify_order_id = Column(String, nullable=True)
    shopify_order_name = Column(String(100), nullable=True)
    shopify_updated_at = Column(DateTime, nullable=True)
    shopify_currency = Column(String(3), nullable=True)
    shopify_financial_status = Column(String(40), nullable=True)
    shopify_fulfillment_status = Column(String(40), nullable=True)
    shopify_total_price = Column(Float, nullable=True)
    shopify_original_total_price = Column(Float, nullable=True)
    shopify_subtotal_price = Column(Float, nullable=True)
    shopify_total_discounts = Column(Float, nullable=True)
    shopify_total_tax = Column(Float, nullable=True)
    shopify_total_refunded = Column(Float, nullable=True)
    shopify_shipping_price = Column(Float, nullable=True)
    shopify_cancelled_at = Column(DateTime, nullable=True)

    instagram_order_id = Column(String, nullable=True)

    discord_tracking_id = Column(String, nullable=True)

    discord_message_id = Column(String, nullable=True)

    # ===================================
    # CUSTOMER
    # ===================================

    customer_name = Column(String)

    customer_phone = Column(String)

    city = Column(String)

    province = Column(String, nullable=True)

    address = Column(String)

    # ===================================
    # PRODUCT SUMMARY
    # ===================================

    product_name = Column(String)

    sku = Column(String, nullable=True)

    size = Column(String, nullable=True)

    quantity = Column(Integer, default=1)

    # ===================================
    # DELIVERY INTELLIGENCE
    # ===================================

    weight_kg = Column(Float, default=0)

    # ===================================
    # FINANCIALS
    # ===================================

    selling_price = Column(Float, default=0)

    product_cost = Column(Float, default=0)

    delivery_cost = Column(Float, default=0)

    packaging_cost = Column(Float, default=0)

    marketing_cost = Column(Float, default=0)

    other_expense = Column(Float, default=0)

    total_cost = Column(Float, default=0)

    net_profit = Column(Float, default=0)

    profit_margin = Column(Float, default=0)

    # ===================================
    # OPERATIONAL
    # ===================================

    source = Column(String)

    status = Column(String, default="PENDING")

    discord_channel = Column(String, nullable=True)

    # ===================================
    # TIMESTAMPS
    # ===================================

    discord_created_at = Column(DateTime, nullable=True, index=True)

    # ===================================
    # PERMANENT ORDER DATE
    # ===================================

    confirmed_order_date = Column(DateTime, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ===================================
    # RELATIONSHIPS
    # ===================================

    items = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
