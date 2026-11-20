"""add tenant-scoped Meta insight sync state, history, and daily rows

Revision ID: 20261122_0008
Revises: 20261121_0007
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261122_0008"
down_revision: Union[str, None] = "20261121_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meta_sync_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selected_account_id", sa.String(length=64), nullable=True),
        sa.Column("running_since", sa.DateTime(), nullable=True),
        sa.Column("active_run_id", sa.Integer(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("business_id", name="uq_meta_sync_state_business"),
    )
    op.create_table(
        "meta_sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("records_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_category", sa.String(length=40), nullable=True),
        sa.Column("error_summary", sa.String(length=300), nullable=True),
        sa.CheckConstraint("status IN ('running', 'completed', 'partially_completed', 'failed')", name="ck_meta_sync_runs_status"),
        sa.CheckConstraint("start_date <= end_date", name="ck_meta_sync_runs_date_range"),
    )
    op.create_index("ix_meta_sync_runs_business_id", "meta_sync_runs", ["business_id"])
    op.create_index("ix_meta_sync_runs_user_id", "meta_sync_runs", ["user_id"])
    op.create_index("ix_meta_sync_runs_business_started", "meta_sync_runs", ["business_id", "started_at"])

    op.create_table(
        "meta_ad_insights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("entity_name", sa.String(length=255), nullable=True),
        sa.Column("campaign_id", sa.String(length=64), nullable=True),
        sa.Column("campaign_name", sa.String(length=255), nullable=True),
        sa.Column("adset_id", sa.String(length=64), nullable=True),
        sa.Column("adset_name", sa.String(length=255), nullable=True),
        sa.Column("ad_id", sa.String(length=64), nullable=True),
        sa.Column("ad_name", sa.String(length=255), nullable=True),
        sa.Column("date_start", sa.Date(), nullable=False),
        sa.Column("date_stop", sa.Date(), nullable=False),
        sa.Column("spend", sa.Numeric(20, 6), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("inline_link_clicks", sa.Integer(), nullable=True),
        sa.Column("ctr", sa.Numeric(20, 8), nullable=True),
        sa.Column("cpc", sa.Numeric(20, 8), nullable=True),
        sa.Column("cpm", sa.Numeric(20, 8), nullable=True),
        sa.Column("frequency", sa.Numeric(20, 8), nullable=True),
        sa.Column("actions_json", sa.Text(), nullable=True),
        sa.Column("action_values_json", sa.Text(), nullable=True),
        sa.Column("cost_per_action_type_json", sa.Text(), nullable=True),
        sa.Column("action_attribution_windows_json", sa.Text(), nullable=False, server_default='["default"]'),
        sa.Column("action_report_time", sa.String(length=16), nullable=False, server_default="mixed"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("level IN ('account', 'campaign', 'adset', 'ad')", name="ck_meta_insights_level"),
        sa.CheckConstraint("date_start <= date_stop", name="ck_meta_insights_date_range"),
        sa.UniqueConstraint(
            "business_id", "account_id", "level", "entity_id", "date_start", "date_stop",
            name="uq_meta_insight_business_identity_day",
        ),
    )
    op.create_index("ix_meta_ad_insights_business_id", "meta_ad_insights", ["business_id"])
    op.create_index("ix_meta_ad_insights_business_dates", "meta_ad_insights", ["business_id", "date_start", "date_stop"])
    op.create_index("ix_meta_ad_insights_business_level", "meta_ad_insights", ["business_id", "level"])


def downgrade() -> None:
    op.drop_table("meta_ad_insights")
    op.drop_table("meta_sync_runs")
    op.drop_table("meta_sync_state")
