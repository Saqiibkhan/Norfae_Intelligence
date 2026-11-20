from datetime import datetime

from sqlalchemy import (
    CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String,
    Text, UniqueConstraint,
)

from app.core.database import Base


class MetaSyncState(Base):
    __tablename__ = "meta_sync_state"
    __table_args__ = (
        UniqueConstraint("business_id", name="uq_meta_sync_state_business"),
    )

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    selected_account_id = Column(String(64), nullable=True)
    running_since = Column(DateTime, nullable=True)
    active_run_id = Column(Integer, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)


class MetaSyncRun(Base):
    __tablename__ = "meta_sync_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'completed', 'partially_completed', 'failed')", name="ck_meta_sync_runs_status"),
        CheckConstraint("start_date <= end_date", name="ck_meta_sync_runs_date_range"),
    )

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    account_id = Column(String(64), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(30), nullable=False)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    records_fetched = Column(Integer, nullable=False, default=0)
    records_created = Column(Integer, nullable=False, default=0)
    records_updated = Column(Integer, nullable=False, default=0)
    records_skipped = Column(Integer, nullable=False, default=0)
    error_category = Column(String(40), nullable=True)
    error_summary = Column(String(300), nullable=True)


Index("ix_meta_sync_runs_business_started", MetaSyncRun.business_id, MetaSyncRun.started_at)


class MetaAdInsight(Base):
    __tablename__ = "meta_ad_insights"
    __table_args__ = (
        CheckConstraint("level IN ('account', 'campaign', 'adset', 'ad')", name="ck_meta_insights_level"),
        CheckConstraint("date_start <= date_stop", name="ck_meta_insights_date_range"),
        UniqueConstraint(
            "business_id", "account_id", "level", "entity_id", "date_start", "date_stop",
            name="uq_meta_insight_business_identity_day",
        ),
        Index("ix_meta_ad_insights_business_dates", "business_id", "date_start", "date_stop"),
        Index("ix_meta_ad_insights_business_level", "business_id", "level"),
    )

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(String(64), nullable=False)
    currency = Column(String(3), nullable=True)
    level = Column(String(16), nullable=False)
    entity_id = Column(String(64), nullable=False)
    entity_name = Column(String(255), nullable=True)
    campaign_id = Column(String(64), nullable=True)
    campaign_name = Column(String(255), nullable=True)
    adset_id = Column(String(64), nullable=True)
    adset_name = Column(String(255), nullable=True)
    ad_id = Column(String(64), nullable=True)
    ad_name = Column(String(255), nullable=True)
    date_start = Column(Date, nullable=False)
    date_stop = Column(Date, nullable=False)
    spend = Column(Numeric(20, 6), nullable=True)
    impressions = Column(Integer, nullable=True)
    reach = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    inline_link_clicks = Column(Integer, nullable=True)
    ctr = Column(Numeric(20, 8), nullable=True)
    cpc = Column(Numeric(20, 8), nullable=True)
    cpm = Column(Numeric(20, 8), nullable=True)
    frequency = Column(Numeric(20, 8), nullable=True)
    actions_json = Column(Text, nullable=True)
    action_values_json = Column(Text, nullable=True)
    cost_per_action_type_json = Column(Text, nullable=True)
    action_attribution_windows_json = Column(Text, nullable=False, default='["default"]')
    action_report_time = Column(String(16), nullable=False, default="mixed")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
