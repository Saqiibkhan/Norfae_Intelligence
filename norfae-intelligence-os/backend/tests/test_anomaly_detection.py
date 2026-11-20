from datetime import date, datetime, timedelta

from app.ai_engine.anomaly_detection_engine import (
    AnomalyDetectionEngine,
    AnomalyThresholds,
)
from app.core.tenant_context import tenant_scope
from app.models import Expense, MetaDailyStats, Order, OrderItem
from app.schemas.anomaly_schema import AnomalyQuery
from app.services.anomaly_detection_service import AnomalyDetectionService


def register(client, email):
    return client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "business_name": email.split("@")[0],
        },
    )


def headers(auth):
    return {
        "Authorization": f"Bearer {auth.json()['access_token']}",
        "X-Business-ID": str(auth.json()["business"]["id"]),
    }


def seed_history(db, target: date):
    historical_days = [target - timedelta(days=days) for days in (28, 25, 22, 19, 16, 13, 10, 1)]
    item_orders = {"prior": [], "current": []}
    counter = 0
    for day in historical_days:
        current_day_orders = []
        for _ in range(5):
            counter += 1
            order = Order(
                internal_order_id=f"ANOM-{counter}",
                status="DELIVERED",
                city="Lahore",
                province="Punjab",
                selling_price=100,
                product_cost=40,
                delivery_cost=10,
                packaging_cost=5,
                marketing_cost=0,
                other_expense=0,
                confirmed_order_date=datetime.combine(day, datetime.min.time()),
            )
            db.add(order)
            current_day_orders.append(order)
        db.flush()
        if day == target - timedelta(days=1):
            item_orders["prior"] = current_day_orders[:3]
        db.add(MetaDailyStats(
            stats_date=day, spend=100, impressions=5000, reach=4000,
            clicks=100, link_clicks=70,
        ))
        db.add(Expense(
            title=f"Shipping costs {day}", category="shipping", source="manual",
            amount=50, expense_date=datetime.combine(day, datetime.min.time()),
        ))

    current_orders = []
    for index in range(10):
        counter += 1
        is_delivered = index < 7
        order = Order(
            internal_order_id=f"ANOM-{counter}",
            status="DELIVERED" if is_delivered else "CANCELLED",
            city="Lahore",
            province="Punjab",
            selling_price=200 if is_delivered else 0,
            product_cost=60 if is_delivered else 0,
            delivery_cost=30 if is_delivered else 0,
            packaging_cost=5 if is_delivered else 0,
            marketing_cost=0,
            other_expense=0,
            confirmed_order_date=datetime.combine(target, datetime.min.time()),
        )
        db.add(order)
        current_orders.append(order)
    db.flush()
    item_orders["current"] = current_orders[:3]
    db.add(MetaDailyStats(
        stats_date=target, spend=200, impressions=5000, reach=4000,
        clicks=25, link_clicks=15,
    ))
    db.add(Expense(
        title="Current shipping costs", category="shipping", source="manual",
        amount=100, expense_date=datetime.combine(target, datetime.min.time()),
    ))
    for kind, orders in item_orders.items():
        for order in orders:
            positive = kind == "prior"
            db.add(OrderItem(
                order_id=order.id,
                product_name="Test product",
                normalized_name="test product",
                sku="SKU-ANOM",
                quantity=1,
                total_price=100 if positive else 20,
                total_cost=50 if positive else 30,
                unit_price=100 if positive else 20,
                unit_cost=50 if positive else 30,
            ))


def test_engine_percentage_baseline_zero_and_minimum_history():
    thresholds = AnomalyThresholds(
        baseline_days=5,
        min_history_points=2,
        z_score_min_points=4,
        order_volume_change_percent=20,
    )
    assert thresholds.order_volume_change_percent == 20
    result = AnomalyDetectionEngine.compare_with_history(
        20, [10, 11], min_history_points=2, change_threshold_percent=50,
        z_score_min_points=14, z_score_threshold=3,
    )
    assert result is not None
    assert result["deviation_percent"] > 80
    assert AnomalyDetectionEngine.compare_with_history(
        20, [10], min_history_points=2, change_threshold_percent=50,
        z_score_min_points=14, z_score_threshold=3,
    ) is None
    assert AnomalyDetectionEngine.compare_with_history(
        10, [0, 0, 0], min_history_points=2, change_threshold_percent=50,
        z_score_min_points=14, z_score_threshold=3,
    ) is None


def test_detection_flags_sales_cost_marketing_city_and_product_anomalies(api_client):
    auth = register(api_client, "anomaly-fixture@example.com")
    business_id = auth.json()["business"]["id"]
    target = date(2026, 9, 30)
    with tenant_scope(business_id), api_client.session_factory() as db:
        seed_history(db, target)
        db.commit()
        service = AnomalyDetectionService()
        report, summary = service.detect(
            db, business_id, AnomalyQuery(start_date=target, end_date=target)
        )
        repeated = service.list_anomalies(
            db, business_id, AnomalyQuery(start_date=target, end_date=target)
        )

    by_metric = {item.metric_name: item for item in report.anomalies}
    assert by_metric["daily_order_count"].observed_value == 10
    assert by_metric["daily_delivered_revenue"].deviation_percent > 100
    assert by_metric["daily_average_order_value"].observed_value == 200
    assert by_metric["delivery_cost_per_delivered_order"].observed_value == 30
    assert by_metric["daily_non_marketing_expenses"].observed_value == 100
    assert by_metric["daily_meta_ad_spend"].observed_value == 200
    assert by_metric["daily_meta_ctr_percent"].observed_value == 0.5
    assert by_metric["daily_meta_cpc"].observed_value == 8
    assert by_metric["daily_cancellation_rate_percent"].observed_value == 30
    assert by_metric["city_delivered_revenue_change"].deviation_percent > 100
    assert by_metric["product_contribution"].observed_value < 0
    assert summary.total == report.total
    assert [item.anomaly_id for item in report.anomalies] == [item.anomaly_id for item in repeated.anomalies]


def test_insufficient_data_zero_denominators_and_missing_period_are_not_fabricated(api_client):
    auth = register(api_client, "anomaly-empty@example.com")
    business_id = auth.json()["business"]["id"]
    target = date(2026, 10, 10)
    with tenant_scope(business_id), api_client.session_factory() as db:
        db.add(Order(
            internal_order_id="ONLY-ONE",
            status="CANCELLED",
            confirmed_order_date=datetime.combine(target, datetime.min.time()),
        ))
        db.add(MetaDailyStats(stats_date=target, spend=0, impressions=0, clicks=0))
        db.commit()
        report, _ = AnomalyDetectionService().detect(
            db, business_id, AnomalyQuery(start_date=target, end_date=target)
        )

    assert report.anomalies == []
    assert report.insufficient_data
    assert "Missing dates are not treated as zero" in report.warnings[0]


def test_api_filters_permissions_and_business_isolation(api_client):
    owner = register(api_client, "anomaly-owner@example.com")
    other = register(api_client, "anomaly-other@example.com")
    target = date(2026, 9, 30)
    business_id = owner.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        seed_history(db, target)
        db.commit()

    base_url = "/intelligence/anomalies?start_date=2026-09-30&end_date=2026-09-30"
    own = api_client.get(base_url, headers=headers(owner))
    sales_only = api_client.get(base_url + "&category=sales", headers=headers(owner))
    summary = api_client.get(
        "/intelligence/anomalies/summary?start_date=2026-09-30&end_date=2026-09-30",
        headers=headers(owner),
    )
    detail_id = own.json()["anomalies"][0]["anomaly_id"]
    detail = api_client.get(
        f"/intelligence/anomalies/{detail_id}?start_date=2026-09-30&end_date=2026-09-30",
        headers=headers(owner),
    )
    foreign_detail = api_client.get(
        f"/intelligence/anomalies/{detail_id}?start_date=2026-09-30&end_date=2026-09-30",
        headers=headers(other),
    )
    invalid_period = api_client.get(
        "/intelligence/anomalies?start_date=2026-10-01&end_date=2026-09-30",
        headers=headers(owner),
    )
    other_tenant = api_client.get(base_url, headers=headers(other))
    unauthenticated = api_client.get(base_url)
    assert own.status_code == 200
    assert own.json()["total"] > 0
    assert sales_only.status_code == 200
    assert all(item["category"] == "sales" for item in sales_only.json()["anomalies"])
    assert summary.status_code == 200
    assert summary.json()["total"] == own.json()["total"]
    assert detail.status_code == 200
    assert detail.json()["anomaly_id"] == detail_id
    assert foreign_detail.status_code == 404
    assert invalid_period.status_code == 422
    assert other_tenant.status_code == 200
    assert other_tenant.json()["anomalies"] == []
    assert unauthenticated.status_code == 401
