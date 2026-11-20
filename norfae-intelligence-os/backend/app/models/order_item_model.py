from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    DateTime
)

from sqlalchemy.orm import (
    relationship
)

from datetime import datetime

from app.core.database import Base


class OrderItem(Base):

    __tablename__ = "order_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "order_id"], ["orders.business_id", "orders.id"],
            name="fk_order_items_business_order", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["business_id", "inventory_product_id"],
            ["inventory_products.business_id", "inventory_products.id"],
            name="fk_order_items_business_inventory",
        ),
    )

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
    # ORDER RELATION
    # ===================================

    order_id = Column(
        Integer
    )

    # ===================================
    # INVENTORY RELATION
    # ===================================

    inventory_product_id = Column(
        Integer,
        nullable=True
    )

    # ===================================
    # PRODUCT INFORMATION
    # ===================================

    product_name = Column(
        String
    )

    normalized_name = Column(
        String,
        index=True
    )

    sku = Column(
        String,
        nullable=True,
        index=True
    )

    variant = Column(
        String,
        nullable=True
    )

    size = Column(
        String,
        nullable=True
    )

    quantity = Column(
        Integer,
        default=1
    )

    # ===================================
    # FINANCIALS
    # ===================================

    unit_price = Column(
        Float,
        default=0
    )

    total_price = Column(
        Float,
        default=0
    )

    unit_cost = Column(
        Float,
        default=0
    )

    total_cost = Column(
        Float,
        default=0
    )

    profit = Column(
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

    # ===================================
    # RELATIONSHIPS
    # ===================================

    order = relationship(
        "Order",
        back_populates="items",
        passive_deletes=True
    )

    inventory_product = relationship(
        "InventoryProduct",
        overlaps="items,order",
    )
