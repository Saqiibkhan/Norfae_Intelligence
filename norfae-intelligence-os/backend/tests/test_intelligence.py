from datetime import datetime

from app.core.tenant_context import tenant_scope
from app.models import Expense, Order, OrderItem, Product
from app.services.data_quality_service import DataQualityService
from app.services.deterministic_profitability_service import DeterministicProfitabilityService
from app.services.product_intelligence_service import ProductIntelligenceService
from app.services.city_intelligence_service import CityIntelligenceService
from app.agents.intelligence_registry import intelligence_agents


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


def test_phase3_agents_are_registered_with_analytics_permission():
    metadata = {agent.agent_id: agent for agent in intelligence_agents.list_agents()}
    assert {"data_analysis", "product_intelligence", "city_intelligence"} <= set(metadata)
    assert metadata["product_intelligence"].required_permission == "analytics:read"
    assert metadata["city_intelligence"].required_permission == "analytics:read"


def test_data_quality_detects_invalid_duplicate_missing_and_suggests_normalization(api_client):
    auth = register(api_client, "quality@example.com")
    business_id = auth.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        db.add_all([
            Product(name=" Shirt ", sku=" sku-1 ", buying_price=-2, selling_price=10, stock=2),
            Product(name="Shirt duplicate", sku="SKU-1", buying_price=4, selling_price=10, stock=2),
            Order(internal_order_id=" O-1 ", product_name="Shirt", sku="missing", quantity=0,
                  selling_price=-1, product_cost=0, delivery_cost=0, packaging_cost=0,
                  marketing_cost=0, other_expense=0, status="MYSTERY", discord_created_at=None),
            Order(internal_order_id="o-1", product_name="Shirt", sku="SKU-1", quantity=1,
                  selling_price=10, product_cost=4, delivery_cost=0, packaging_cost=0,
                  marketing_cost=0, other_expense=0, status="DELIVERED", discord_created_at=datetime(2026, 1, 1)),
        ])
        db.commit()
        report = DataQualityService.analyze(db, business_id)
        original_name = db.query(Product).order_by(Product.id).first().name

    assert report.total_records_inspected == 4
    assert report.invalid_records == 4
    assert report.valid_records == 0
    assert report.missing_fields["order.source_order_date"] == 1
    assert report.duplicate_records["orders.internal_order_id"] == 1
    assert report.duplicate_records["products.sku_case_insensitive"] == 1
    assert any(issue.code == "invalid_quantity" for issue in report.issues)
    assert any(issue.code == "invalid_amount" for issue in report.issues)
    assert any(issue.suggested_value == "Shirt" for issue in report.issues)
    assert any(
        preview.record_type == "product" and preview.normalized_fields.get("name") == "Shirt"
        for preview in report.normalization_preview
    )
    assert any("explicit, audited" in item for item in report.recommended_corrections)
    assert original_name == " Shirt "


def test_data_quality_warns_on_extreme_values_without_marking_them_invalid(api_client):
    auth = register(api_client, "outlier@example.com")
    business_id = auth.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        for index, quantity in enumerate((1, 1, 2, 100)):
            db.add(Order(
                internal_order_id=f"OUTLIER-{index}", product_name="Item", quantity=quantity,
                selling_price=10, product_cost=0, delivery_cost=0, packaging_cost=0,
                marketing_cost=0, other_expense=0, status="DELIVERED",
            ))
        db.commit()
        report = DataQualityService.analyze(db, business_id)

    assert any(issue.code == "unusual_value" and issue.field == "order.quantity" for issue in report.issues)
    assert report.invalid_records == 4  # Missing source order dates, not the outlier, invalidate records.
    assert any("order.quantity" in warning for warning in report.warnings)


def test_data_quality_counts_complete_records_as_valid(api_client):
    auth = register(api_client, "valid-quality@example.com")
    business_id = auth.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        db.add(Product(name="Valid product", sku="VALID-1", buying_price=5,
                       selling_price=10, stock=2, weight_kg=0.3))
        db.add(Order(internal_order_id="VALID-ORDER", product_name="Valid product",
                     sku="VALID-1", quantity=1, selling_price=10, product_cost=5,
                     delivery_cost=0, packaging_cost=0, marketing_cost=0,
                     other_expense=0, status="DELIVERED",
                     confirmed_order_date=datetime(2026, 3, 1)))
        db.commit()
        report = DataQualityService.analyze(db, business_id)

    assert report.total_records_inspected == 2
    assert report.valid_records == 2
    assert report.invalid_records == 0


def test_profitability_formula_prefers_marketing_ledger_without_double_count(api_client):
    auth = register(api_client, "profit@example.com")
    business_id = auth.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        db.add(Order(
            internal_order_id="P-1", status="DELIVERED", confirmed_order_date=datetime(2026, 2, 3),
            selling_price=100, product_cost=30, packaging_cost=5, delivery_cost=10,
            marketing_cost=4, other_expense=0,
        ))
        db.add_all([
            Expense(title="Ad spend", category="marketing", amount=8, expense_date=datetime(2026, 2, 3)),
            Expense(title="Rent", category="rent", amount=2, expense_date=datetime(2026, 2, 3)),
        ])
        db.commit()
        result = DeterministicProfitabilityService.overall(db, business_id)

    assert result.net_revenue.amount == 100
    assert result.gross_revenue.available is False
    assert result.discounts.amount is None and result.refunds.amount is None
    assert result.cost_of_goods_sold.amount == 30
    assert result.packaging_cost.amount == 5
    assert result.delivery_cost.amount == 10
    assert result.advertising_expense.amount == 8
    assert result.other_business_expenses.amount == 2
    assert result.net_profit.amount == 45
    assert result.complete is False
    assert any("only ledger advertising" in warning for warning in result.warnings)


def test_profitability_uses_order_marketing_fallback_and_negative_zero_revenue(api_client):
    auth = register(api_client, "fallback-profit@example.com")
    business_id = auth.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        db.add(Order(
            internal_order_id="P-2", status="DELIVERED", selling_price=0,
            product_cost=0, packaging_cost=2, delivery_cost=0,
            marketing_cost=0, other_expense=3,
        ))
        db.add(Order(internal_order_id="C-1", status="CANCELLED", selling_price=50))
        db.add(Order(internal_order_id="R-1", status="RETURNED", selling_price=30))
        db.commit()
        result = DeterministicProfitabilityService.overall(db, business_id)
        delivered = db.query(Order).filter(Order.internal_order_id == "P-2").one()
        order_result = DeterministicProfitabilityService.order(db, business_id, delivered.id)

    assert result.net_revenue.amount == 0
    assert result.advertising_expense.amount == 0
    assert result.net_profit.amount == -5
    assert result.profit_margin_percent is None
    assert result.cancelled_orders == result.returned_orders == 1
    assert result.complete is False
    assert order_result.net_profit.amount == -5
    assert order_result.profit_margin_percent is None


def test_missing_cost_remains_unavailable_instead_of_becoming_zero(api_client):
    auth = register(api_client, "missing-cost@example.com")
    business_id = auth.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        db.execute(Order.__table__.insert().values(
            business_id=business_id,
            internal_order_id="MISSING-COST",
            status="DELIVERED",
            selling_price=50,
            product_cost=None,
            delivery_cost=0,
            packaging_cost=0,
            marketing_cost=0,
            other_expense=0,
        ))
        db.commit()
        result = DeterministicProfitabilityService.overall(db, business_id)

    assert result.cost_of_goods_sold.amount is None
    assert result.cost_of_goods_sold.available is False
    assert result.net_profit.amount is None
    assert result.net_profit.available is False


def test_product_profitability_and_api_business_isolation(api_client):
    owner_a = register(api_client, "intelligence-a@example.com")
    owner_b = register(api_client, "intelligence-b@example.com")
    business_a = owner_a.json()["business"]["id"]
    with tenant_scope(business_a), api_client.session_factory() as db:
        product = Product(name="A product", sku="A-SKU", buying_price=30, selling_price=60, stock=2)
        db.add(product)
        db.flush()
        order = Order(internal_order_id="A-ORDER", status="DELIVERED", selling_price=120,
                      product_cost=60, packaging_cost=0, delivery_cost=0,
                      marketing_cost=0, other_expense=0)
        db.add(order)
        db.flush()
        db.add(OrderItem(order_id=order.id, product_name="A product", normalized_name="a product",
                         sku="A-SKU", quantity=2, unit_price=60, total_price=120,
                         unit_cost=30, total_cost=60))
        db.commit()
        order_id = order.id
        product_id = product.id

    quality = api_client.get("/intelligence/data-quality", headers=headers(owner_a))
    products = api_client.get("/intelligence/profitability/products", headers=headers(owner_a))
    product_detail = api_client.get(
        f"/intelligence/products/{product_id}", headers=headers(owner_a)
    )
    foreign_order = api_client.get(
        f"/intelligence/profitability/orders/{order_id}", headers=headers(owner_b)
    )
    foreign_product = api_client.get(
        f"/intelligence/products/{product_id}", headers=headers(owner_b)
    )
    unauthorized = api_client.get("/intelligence/profitability")

    assert quality.status_code == 200
    assert quality.json()["total_records_inspected"] == 2
    assert products.status_code == 200
    assert products.json()[0]["revenue"]["amount"] == 120
    assert products.json()[0]["cost_of_goods_sold"]["amount"] == 60
    assert products.json()[0]["contribution_profit"]["amount"] == 60
    assert product_detail.status_code == 200
    assert product_detail.json()["product_contribution"]["amount"] == 60
    assert foreign_order.status_code == 404
    assert foreign_product.status_code == 404
    assert unauthorized.status_code == 401


def test_product_intelligence_aggregation_no_sales_negative_contribution_and_date_filter(api_client):
    owner = register(api_client, "product-intel@example.com")
    business_id = owner.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        sold = Product(name="Loss leader", sku="LOSS-1", buying_price=60, selling_price=50, stock=4)
        no_sales = Product(name="No sales", sku="NONE-1", buying_price=10, selling_price=20, stock=3)
        db.add_all([sold, no_sales])
        db.flush()
        delivered = Order(internal_order_id="PI-DEL", status="DELIVERED", city="Lahore",
                          confirmed_order_date=datetime(2026, 4, 5), selling_price=50,
                          product_cost=60, delivery_cost=4, packaging_cost=2,
                          marketing_cost=0, other_expense=0)
        cancelled = Order(internal_order_id="PI-CAN", status="CANCELLED", city="Lahore",
                          confirmed_order_date=datetime(2026, 4, 7), selling_price=50)
        outside = Order(internal_order_id="PI-OLD", status="DELIVERED", city="Lahore",
                        confirmed_order_date=datetime(2026, 2, 7), selling_price=100,
                        product_cost=10, delivery_cost=0, packaging_cost=0,
                        marketing_cost=0, other_expense=0)
        db.add_all([delivered, cancelled, outside])
        db.flush()
        db.add_all([
            OrderItem(order_id=delivered.id, product_name="Loss leader", sku="LOSS-1", quantity=2,
                      total_price=50, total_cost=60),
            OrderItem(order_id=cancelled.id, product_name="Loss leader", sku="LOSS-1", quantity=1,
                      total_price=50, total_cost=60),
            OrderItem(order_id=outside.id, product_name="Loss leader", sku="LOSS-1", quantity=4,
                      total_price=100, total_cost=10),
        ])
        db.commit()
        report = ProductIntelligenceService.analyze_business(
            db, business_id, datetime(2026, 4, 1).date(), datetime(2026, 4, 30).date()
        )

    assert report.total_products == 2
    loss = next(product for product in report.products if product.sku == "LOSS-1")
    no_sales_result = next(product for product in report.products if product.sku == "NONE-1")
    assert loss.total_units_sold == 2
    assert loss.order_count == 2
    assert loss.delivered_orders == 1
    assert loss.cancelled_orders == 1
    assert loss.revenue.amount == 50
    assert loss.recorded_product_cost.amount == 60
    assert loss.product_contribution.amount == -10
    assert loss.performance_status == "negative_contribution"
    assert loss.average_selling_price == 25
    assert no_sales_result.performance_status == "no_sales"
    assert no_sales_result.total_units_sold == 0
    assert no_sales_result.product_contribution.amount == 0
    assert no_sales_result.contribution_margin_percent is None
    assert report.best_performing_product_id == loss.product_id


def test_product_intelligence_does_not_guess_between_duplicate_normalized_skus(api_client):
    owner = register(api_client, "duplicate-products@example.com")
    business_id = owner.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        db.add_all([
            Product(name="First", sku="DUP-1", buying_price=1, selling_price=10, stock=2),
            Product(name="Second", sku="dup-1", buying_price=2, selling_price=10, stock=2),
        ])
        db.flush()
        order = Order(internal_order_id="DUP-ORDER", status="DELIVERED", selling_price=10,
                      product_cost=1, delivery_cost=0, packaging_cost=0,
                      marketing_cost=0, other_expense=0)
        db.add(order)
        db.flush()
        db.add(OrderItem(order_id=order.id, product_name="First", sku="DUP-1",
                         quantity=1, total_price=10, total_cost=1))
        db.commit()
        report = ProductIntelligenceService.analyze_business(db, business_id)

    assert all(product.order_count == 0 for product in report.products)
    assert any("duplicate normalized SKUs=1" in warning for warning in report.warnings)
    assert any("ambiguously matched" in warning for warning in report.warnings)


def test_city_intelligence_groups_missing_city_compares_cost_and_isolates_business(api_client):
    owner = register(api_client, "city-intel@example.com")
    other = register(api_client, "other-city-intel@example.com")
    business_id = owner.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        db.add_all([
            Order(internal_order_id="L-1", status="DELIVERED", city="Lahore", province="Punjab",
                  confirmed_order_date=datetime(2026, 5, 1), selling_price=100, product_cost=40,
                  delivery_cost=10, packaging_cost=5, marketing_cost=0, other_expense=0),
            Order(internal_order_id="L-2", status="DELIVERED", city="Lahore", province="Punjab",
                  confirmed_order_date=datetime(2026, 5, 2), selling_price=150, product_cost=60,
                  delivery_cost=20, packaging_cost=5, marketing_cost=0, other_expense=0),
            Order(internal_order_id="K-1", status="CANCELLED", city="Karachi", province="Sindh",
                  confirmed_order_date=datetime(2026, 5, 2), selling_price=50, delivery_cost=3),
            Order(internal_order_id="U-1", status="DELIVERED", city=None, province=None,
                  confirmed_order_date=datetime(2026, 5, 3), selling_price=30, product_cost=35,
                  delivery_cost=8, packaging_cost=0, marketing_cost=0, other_expense=0),
            Order(internal_order_id="OLD-1", status="DELIVERED", city="Lahore", province="Punjab",
                  confirmed_order_date=datetime(2026, 3, 1), selling_price=999, product_cost=1,
                  delivery_cost=1, packaging_cost=1, marketing_cost=0, other_expense=0),
        ])
        db.commit()
        report = CityIntelligenceService.analyze_business(
            db, business_id, datetime(2026, 5, 1).date(), datetime(2026, 5, 31).date()
        )

    lahore = next(city for city in report.cities if city.city == "Lahore")
    karachi = next(city for city in report.cities if city.city == "Karachi")
    unknown = next(city for city in report.cities if city.city is None)
    assert lahore.total_orders == 2
    assert lahore.total_revenue.amount == 250
    assert lahore.average_order_value == 125
    assert lahore.recorded_delivery_costs.amount == 30
    assert lahore.delivery_cost_per_delivered_order == 15
    assert lahore.product_contribution.amount == 150
    assert lahore.estimated_order_profit.amount == 110
    assert lahore.unallocated_business_expenses.available is False
    assert report.best_performing_city == "Lahore"
    assert karachi.cancelled_orders == 1
    assert unknown.city is None
    assert any("Unknown city bucket" in warning for warning in report.warnings)

    product_list = api_client.get("/intelligence/products", headers=headers(owner))
    city_list = api_client.get("/intelligence/cities", headers=headers(owner))
    city_detail = api_client.get(
        "/intelligence/cities/Lahore?start_date=2026-05-01&end_date=2026-05-31",
        headers=headers(owner),
    )
    foreign_city = api_client.get("/intelligence/cities/Lahore", headers=headers(other))
    membership = api_client.post(
        f"/businesses/{business_id}/memberships",
        json={"email": "other-city-intel@example.com", "role": "viewer"},
        headers=headers(owner),
    )
    viewer_city_list = api_client.get(
        "/intelligence/cities",
        headers={
            "Authorization": f"Bearer {other.json()['access_token']}",
            "X-Business-ID": str(business_id),
        },
    )
    assert product_list.status_code == city_list.status_code == city_detail.status_code == 200
    assert city_detail.json()["matches"][0]["total_revenue"]["amount"] == 250
    assert foreign_city.status_code == 404
    assert membership.status_code == 201
    assert viewer_city_list.status_code == 200


def test_intelligence_empty_datasets_and_date_period_validation(api_client):
    owner = register(api_client, "empty-intelligence@example.com")
    business_id = owner.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        products = ProductIntelligenceService.analyze_business(db, business_id)
        cities = CityIntelligenceService.analyze_business(db, business_id)

    assert products.total_products == 0 and products.products == []
    assert cities.total_cities == 0 and cities.cities == []
    assert cities.warnings
    invalid_dates = api_client.get(
        "/intelligence/products?start_date=2026-06-10&end_date=2026-06-01",
        headers=headers(owner),
    )
    assert invalid_dates.status_code == 422


def test_product_and_city_unusual_change_requires_sufficient_history(api_client):
    owner = register(api_client, "trend-intelligence@example.com")
    business_id = owner.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        product = Product(name="Trend product", sku="TREND-1", buying_price=20,
                          selling_price=100, stock=20)
        db.add(product)
        db.flush()
        for period_date, price, prefix in (
            (datetime(2026, 6, 28), 50, "PREV"),
            (datetime(2026, 6, 29), 50, "PREV"),
            (datetime(2026, 6, 30), 50, "PREV"),
            (datetime(2026, 7, 1), 100, "CURR"),
            (datetime(2026, 7, 2), 100, "CURR"),
            (datetime(2026, 7, 3), 100, "CURR"),
        ):
            order = Order(internal_order_id=f"{prefix}-{period_date.day}", status="DELIVERED",
                          city="Trendville", province="Punjab", confirmed_order_date=period_date,
                          selling_price=price, product_cost=price / 2, delivery_cost=1,
                          packaging_cost=0, marketing_cost=0, other_expense=0)
            db.add(order)
            db.flush()
            db.add(OrderItem(order_id=order.id, product_name="Trend product", sku="TREND-1",
                             quantity=1, total_price=price, total_cost=price / 2))
        db.commit()
        products = ProductIntelligenceService.analyze_business(
            db, business_id, datetime(2026, 7, 1).date(), datetime(2026, 7, 3).date()
        )
        cities = CityIntelligenceService.analyze_business(
            db, business_id, datetime(2026, 7, 1).date(), datetime(2026, 7, 3).date()
        )

    product_result = products.products[0]
    city_result = cities.cities[0]
    assert product_result.previous_period_revenue_change_percent == 100
    assert product_result.unusual_performance_change is True
    assert city_result.previous_period_revenue_change_percent == 100
    assert city_result.unusual_performance_change is True
