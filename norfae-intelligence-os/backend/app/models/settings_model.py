from sqlalchemy import Column, ForeignKey, Integer, Float, String, UniqueConstraint

from app.core.database import Base


class SettingsModel(Base):

    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("business_id", name="uq_settings_business_id"),)

    # ===================================
    # PRIMARY
    # ===================================

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)

    # ===================================
    # TAXES
    # ===================================

    gst_percentage = Column(Float, default=16)

    fuel_surcharge_percentage = Column(Float, default=30)

    income_tax_percentage = Column(Float, default=4)

    # ===================================
    # OPERATIONS
    # ===================================

    packaging_cost = Column(Float, default=50)

    warehouse_city = Column(String, default="Lahore")

    warehouse_province = Column(String, default="Punjab")

    # ===================================
    # SHOPIFY
    # ===================================

    shopify_store_url = Column(String, nullable=True)

    shopify_access_token = Column(String, nullable=True)

    # ===================================
    # META ADS
    # ===================================

    meta_account_id = Column(String, nullable=True)

    meta_access_token = Column(String, nullable=True)

    # ===================================
    # SAME CITY
    # ===================================

    same_city_half_kg = Column(Float, default=100)

    same_city_one_kg = Column(Float, default=140)

    same_city_additional_half_kg = Column(Float, default=40)

    # ===================================
    # SAME PROVINCE
    # ===================================

    same_province_half_kg = Column(Float, default=120)

    same_province_one_kg = Column(Float, default=160)

    same_province_additional_half_kg = Column(Float, default=50)

    # ===================================
    # OTHER PROVINCE
    # ===================================

    other_province_half_kg = Column(Float, default=140)

    other_province_one_kg = Column(Float, default=190)

    other_province_additional_half_kg = Column(Float, default=60)
