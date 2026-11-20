from datetime import date, datetime
from decimal import Decimal

from app.core.tenant_context import tenant_scope
from app.models import Expense, MetaDailyStats, Order, SettingsModel
from app.services.marketing_intelligence_service import _rate
from app.services.marketing_intelligence_service import MarketingIntelligenceService
from app.services.meta_ads_service import MetaAdsService


def register(client, email):
    return client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "business_name": email.split("@")[0],
        },
    )


def headers(auth, business_id=None):
    return {
        "Authorization": f"Bearer {auth.json()['access_token']}",
        "X-Business-ID": str(business_id or auth.json()["business"]["id"]),
    }


def test_metric_formulas_zero_and_missing_denominators():
    assert _rate(Decimal("25"), Decimal("200"), Decimal("100")) == 12.5
    assert _rate(Decimal("50"), Decimal("10")) == 5.0
    assert _rate(Decimal("50"), Decimal("1000"), Decimal("1000")) == 50.0
    assert _rate(Decimal("10"), Decimal("0")) is None
    assert _rate(Decimal("10"), None) is None


def test_overview_deduplicates_meta_expense_ledger_and_keeps_other_marketing_separate(api_client):
    auth = register(api_client, "marketing-overview@example.com")
    business_id = auth.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        db.add_all([
            MetaDailyStats(stats_date=date(2026, 8, 1), spend=100, impressions=1000,
                           reach=800, clicks=100, link_clicks=60, leads=10,
                           instagram_messages=5),
            MetaDailyStats(stats_date=date(2026, 8, 2), spend=50, impressions=1000,
                           reach=750, clicks=100, link_clicks=60, leads=4,
                           instagram_messages=2),
            Expense(title="Meta August 1", category="marketing", source="meta",
                    external_reference="meta_2026-08-01", amount=100,
                    expense_date=datetime(2026, 8, 1)),
            Expense(title="Meta August 2", category="marketing", source="meta",
                    external_reference="meta_2026-08-02", amount=50,
                    expense_date=datetime(2026, 8, 2)),
            Expense(title="Other marketing", category="marketing", source="manual",
                    amount=25, expense_date=datetime(2026, 8, 1)),
            Order(internal_order_id="MKT-ORDER", status="DELIVERED", selling_price=200,
                  product_cost=80, delivery_cost=10, packaging_cost=5,
                  marketing_cost=0, other_expense=0,
                  confirmed_order_date=datetime(2026, 8, 1)),
        ])
        db.commit()
        overview = MarketingIntelligenceService.overview(
            db, business_id, date(2026, 8, 1), date(2026, 8, 2)
        )
        first_day = MarketingIntelligenceService.overview(
            db, business_id, date(2026, 8, 1), date(2026, 8, 1)
        )
        trend = MarketingIntelligenceService.trends(
            db, business_id, date(2026, 8, 1), date(2026, 8, 2)
        )

    assert overview.spend.amount == 150
    assert overview.meta_expense_ledger_spend.amount == 150
    assert overview.meta_ledger_overlap_amount.amount == 150
    assert overview.overlap_days == 2
    assert overview.other_marketing_expenses.amount == 25
    assert overview.impressions.amount == 2000
    assert overview.reach.amount == 1550
    assert overview.clicks.amount == 200
    assert overview.link_clicks.amount == 120
    assert overview.leads.amount == 14
    assert overview.ctr_percent == 10
    assert overview.cpc == 0.75
    assert overview.cpm == 75
    assert overview.attributed_purchase_count.available is False
    assert overview.attributed_conversion_value.available is False
    assert overview.cpa is None and overview.roas is None
    assert overview.observed_business_revenue.amount == 200
    assert "not be interpreted as Meta-attributed" in overview.observed_revenue_attribution_note
    assert first_day.spend.amount == 100
    assert len(trend.points) == 2


def test_overview_uses_meta_expense_fallback_when_daily_stats_are_missing(api_client):
    auth = register(api_client, "marketing-fallback@example.com")
    business_id = auth.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        db.add(Expense(title="Synced Meta", category="marketing", source="meta",
                       external_reference="meta_2026-08-03", amount=42,
                       expense_date=datetime(2026, 8, 3)))
        db.commit()
        report = MarketingIntelligenceService.overview(
            db, business_id, date(2026, 8, 3), date(2026, 8, 3)
        )

    assert report.spend.amount == 42
    assert report.spend.source.startswith("MetaDailyStats")
    assert report.impressions.available is False
    assert report.ctr_percent is None
    assert report.cpa is None and report.roas is None


def test_empty_marketing_dataset_has_unavailable_metrics_not_invented_zeros(api_client):
    auth = register(api_client, "marketing-empty@example.com")
    business_id = auth.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        report = MarketingIntelligenceService.overview(db, business_id)
        trend = MarketingIntelligenceService.trends(db, business_id)

    assert report.spend.available is False
    assert report.impressions.available is False
    assert report.ctr_percent is None
    assert report.observed_business_revenue.available is False
    assert trend.points == []
    assert trend.warnings


def test_campaign_metrics_comparison_recommendations_and_missing_conversion_value(api_client, monkeypatch):
    auth = register(api_client, "marketing-campaigns@example.com")
    business_id = auth.json()["business"]["id"]
    current_start = date(2026, 8, 10)
    previous_start = date(2026, 8, 3)
    with tenant_scope(business_id), api_client.session_factory() as db:
        db.add(SettingsModel(meta_account_id="act-test", meta_access_token="not-a-real-token"))
        db.commit()

        def fake_campaigns(_db, start_date=None, end_date=None):
            if start_date == previous_start.isoformat():
                return {"success": True, "campaigns": [
                    {"campaign_id": "c1", "campaign_name": "Campaign One", "spend": 40,
                     "impressions": 1000, "reach": 900, "clicks": 200, "link_clicks": 100,
                     "sales": 4, "purchase_data_available": True, "leads": 1,
                     "instagram_messages": 0},
                    {"campaign_id": "c2", "campaign_name": "No purchases", "spend": 12,
                     "impressions": 1000, "reach": 800, "clicks": 30, "link_clicks": 20,
                     "sales": 0, "purchase_data_available": True, "leads": 0,
                     "instagram_messages": 0},
                ]}
            return {"success": True, "campaigns": [
                {"campaign_id": "c1", "campaign_name": "Campaign One", "spend": 100,
                 "impressions": 1000, "reach": 900, "clicks": 100, "link_clicks": 70,
                 "sales": 10, "purchase_data_available": True, "leads": 2,
                 "instagram_messages": 0},
                {"campaign_id": "c2", "campaign_name": "No purchases", "spend": 20,
                 "impressions": 1000, "reach": 800, "clicks": 30, "link_clicks": 20,
                 "sales": 0, "purchase_data_available": True, "leads": 0,
                 "instagram_messages": 0},
                {"campaign_id": "c3", "campaign_name": "No action field", "spend": 25,
                 "impressions": 1200, "reach": 1000, "clicks": 40, "link_clicks": 25,
                 "sales": 0, "purchase_data_available": False, "leads": 0,
                 "instagram_messages": 0},
            ]}

        monkeypatch.setattr(MetaAdsService, "get_campaigns", staticmethod(fake_campaigns))
        page = MarketingIntelligenceService.campaigns(
            db, business_id, current_start, date(2026, 8, 16), page_size=10
        )

    campaign = next(item for item in page.campaigns if item.entity_id == "c1")
    no_sales = next(item for item in page.campaigns if item.entity_id == "c2")
    no_action = next(item for item in page.campaigns if item.entity_id == "c3")
    assert campaign.ctr_percent == 10
    assert campaign.cpc == 1
    assert campaign.cpm == 100
    assert campaign.cpa == 10
    assert campaign.roas is None
    assert campaign.attributed_purchase_count.amount == 10
    assert campaign.attributed_conversion_value.available is False
    assert campaign.previous_spend_change_percent == 150
    assert campaign.previous_ctr_change_percent == -50
    assert campaign.unusual_spend_change is True
    assert any("CTR decline" in recommendation for recommendation in campaign.recommendations)
    assert no_sales.cpa is None
    assert any("no purchase actions" in recommendation for recommendation in no_sales.recommendations)
    assert no_action.attributed_purchase_count.available is False
    assert any("Verify Meta purchase-event" in recommendation for recommendation in no_action.recommendations)


def test_campaign_api_is_tenant_scoped_and_viewer_can_read(api_client, monkeypatch):
    owner = register(api_client, "marketing-api-owner@example.com")
    viewer = register(api_client, "marketing-api-viewer@example.com")
    business_id = owner.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        db.add(SettingsModel(meta_account_id="act-test", meta_access_token="not-a-real-token"))
        db.commit()
    membership = api_client.post(
        f"/businesses/{business_id}/memberships",
        json={"email": "marketing-api-viewer@example.com", "role": "viewer"},
        headers=headers(owner),
    )
    assert membership.status_code == 201

    def fake_campaigns(_db, start_date=None, end_date=None):
        return {"success": True, "campaigns": [
            {"campaign_id": "tenant-campaign", "campaign_name": "Tenant campaign",
             "spend": 20, "impressions": 300, "reach": 250, "clicks": 20,
             "link_clicks": 15, "sales": 0, "purchase_data_available": True,
             "leads": 0, "instagram_messages": 0},
        ]}

    monkeypatch.setattr(MetaAdsService, "get_campaigns", staticmethod(fake_campaigns))
    viewer_headers = headers(viewer, business_id)
    response = api_client.get("/intelligence/marketing/campaigns", headers=viewer_headers)
    forged = api_client.get(
        "/intelligence/marketing/overview",
        headers=headers(viewer, owner.json()["business"]["id"] + 999),
    )
    unauthorized = api_client.get("/intelligence/marketing/overview")

    assert response.status_code == 200
    assert response.json()["campaigns"][0]["entity_id"] == "tenant-campaign"
    assert forged.status_code == 404
    assert unauthorized.status_code == 401

