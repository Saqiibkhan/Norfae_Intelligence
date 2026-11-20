from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Index

from app.core.database import Base


class ShopifySyncState(Base):
    __tablename__ = "shopify_sync_state"
    __table_args__ = (UniqueConstraint("business_id", name="uq_shopify_sync_state_business"),)

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    store_domain = Column(String(255), nullable=True)
    products_cursor = Column(DateTime, nullable=True)
    orders_cursor = Column(DateTime, nullable=True)
    products_running_since = Column(DateTime, nullable=True)
    orders_running_since = Column(DateTime, nullable=True)


class ShopifySyncRun(Base):
    __tablename__ = "shopify_sync_runs"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    sync_type = Column(String(20), nullable=False)
    trigger_type = Column(String(20), nullable=False, default="manual")
    status = Column(String(30), nullable=False)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    records_fetched = Column(Integer, nullable=False, default=0)
    records_created = Column(Integer, nullable=False, default=0)
    records_updated = Column(Integer, nullable=False, default=0)
    records_skipped = Column(Integer, nullable=False, default=0)
    error_category = Column(String(40), nullable=True)
    error_summary = Column(String(300), nullable=True)
    cursor_before = Column(DateTime, nullable=True)
    cursor_after = Column(DateTime, nullable=True)


Index("ix_shopify_sync_runs_business_started", ShopifySyncRun.business_id, ShopifySyncRun.started_at)
