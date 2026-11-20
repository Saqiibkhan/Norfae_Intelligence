from sqlalchemy import Column, ForeignKey, Integer, Float, Date, DateTime, UniqueConstraint

from datetime import datetime

from app.core.database import Base
from app.core.timezone import pakistan_now


class MetaDailyStats(Base):

    __tablename__ = "meta_daily_stats"
    __table_args__ = (UniqueConstraint("business_id", "stats_date", name="uq_meta_daily_stats_business_date"),)

    # ===================================
    # PRIMARY
    # ===================================

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)

    # ===================================
    # DATE
    # ===================================

    stats_date = Column(Date, index=True)

    # ===================================
    # SPEND
    # ===================================

    spend = Column(Float, default=0)

    # ===================================
    # TRAFFIC
    # ===================================

    impressions = Column(Integer, default=0)

    reach = Column(Integer, default=0)

    clicks = Column(Integer, default=0)

    link_clicks = Column(Integer, default=0)

    landing_page_views = Column(Integer, default=0)

    # ===================================
    # PERFORMANCE
    # ===================================

    ctr = Column(Float, default=0)

    cpc = Column(Float, default=0)

    cpm = Column(Float, default=0)

    frequency = Column(Float, default=0)

    # ===================================
    # INSTAGRAM
    # ===================================

    instagram_messages = Column(Integer, default=0)

    cost_per_instagram_message = Column(Float, default=0)

    # ===================================
    # LEADS
    # ===================================

    leads = Column(Integer, default=0)

    # ===================================
    # BUSINESS ANALYTICS
    # ===================================

    discord_orders = Column(Integer, default=0)

    shopify_orders = Column(Integer, default=0)

    total_orders = Column(Integer, default=0)

    # ===================================
    # PROFIT ANALYTICS
    # ===================================

    gross_revenue = Column(Float, default=0)

    net_profit = Column(Float, default=0)

    # ===================================
    # TIMESTAMPS
    # ===================================

    created_at = Column(DateTime, default=pakistan_now)
