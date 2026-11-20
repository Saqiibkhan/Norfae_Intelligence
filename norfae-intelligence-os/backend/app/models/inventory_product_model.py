from sqlalchemy import Column, ForeignKey, Integer, String, Float, DateTime, UniqueConstraint

from datetime import datetime

from app.core.database import Base


class InventoryProduct(Base):

    __tablename__ = "inventory_products"
    __table_args__ = (
        UniqueConstraint("business_id", "id", name="uq_inventory_products_business_id_id"),
        UniqueConstraint("business_id", "sku", name="uq_inventory_products_business_sku"),
        UniqueConstraint("business_id", "shopify_variant_id", name="uq_inventory_business_shopify_variant"),
    )

    # ===================================
    # PRIMARY
    # ===================================

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)

    # ===================================
    # PRODUCT IDENTITY
    # ===================================

    product_name = Column(String, index=True)

    normalized_name = Column(String, index=True)

    sku = Column(String, index=True)

    category = Column(String, nullable=True)

    variant = Column(String, nullable=True)

    size = Column(String, nullable=True)

    # ===================================
    # INVENTORY
    # ===================================

    stock_quantity = Column(Integer, default=0)

    low_stock_threshold = Column(Integer, default=5)

    # ===================================
    # FINANCIALS
    # ===================================

    product_cost = Column(Float, default=0)

    selling_price = Column(Float, default=0)

    # ===================================
    # DELIVERY INTELLIGENCE
    # ===================================

    weight_kg = Column(Float, nullable=True)
    # ===================================
    # SHOPIFY
    # ===================================

    shopify_product_id = Column(String, nullable=True)

    shopify_variant_id = Column(String, nullable=True)
    shopify_sku = Column(String, nullable=True)
    shopify_status = Column(String, nullable=True)
    shopify_updated_at = Column(DateTime, nullable=True)
    shopify_created_at = Column(DateTime, nullable=True)
    shopify_compare_at_price = Column(Float, nullable=True)
    shopify_image_url = Column(String(2048), nullable=True)

    # ===================================
    # TIMESTAMPS
    # ===================================

    created_at = Column(DateTime, default=datetime.utcnow)
