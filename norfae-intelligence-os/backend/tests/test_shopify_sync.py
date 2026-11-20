from datetime import datetime
from types import SimpleNamespace

import pytest
import requests
from sqlalchemy import event

from app.core.tenant_context import tenant_scope
from app.models import InventoryProduct, Order, OrderItem, Product, SettingsModel, ShopifySyncRun, ShopifySyncState
from app.services.shopify_client import ShopifyAPIError, ShopifyClient
from app.services.shopify_sync_service import ShopifySyncService
from app.services.deterministic_profitability_service import DeterministicProfitabilityService


def register(client, email):
    return client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "business_name": email.split("@")[0]})


def headers(auth):
    return {"Authorization": f"Bearer {auth.json()['access_token']}", "X-Business-ID": str(auth.json()["business"]["id"])}


def configure_shopify(client, auth, store="catalog.myshopify.com", token="test-shopify-token"):
    result = client.put("/settings/integrations", headers=headers(auth), json={"shopify_store_url": store, "shopify_access_token": token})
    assert result.status_code == 200, result.text


def product_payload(*, variant_id="301", sku="SKU-1", price="25.00", inventory=8, title="Shopify Jacket"):
    return {"id": 201, "title": title, "body_html": "Imported description", "vendor": "Vendor",
            "product_type": "Apparel", "status": "active", "created_at": "2026-01-01T00:00:00Z",
            "image": {"src": "https://cdn.shopify.com/s/files/jacket.jpg"},
            "updated_at": "2026-11-20T10:00:00Z", "variants": [{"id": variant_id, "title": "Blue / M",
            "sku": sku, "price": price, "compare_at_price": "30.00", "inventory_quantity": inventory}]}


def order_payload(*, status="open", fulfillment=None, cancelled_at=None, total="60.00", financial_status="paid", refunds=None):
    return {"id": 901, "name": "#1001", "created_at": "2026-11-18T12:00:00Z", "updated_at": "2026-11-20T12:00:00Z",
            "currency": "USD", "financial_status": financial_status, "fulfillment_status": fulfillment,
            "cancelled_at": cancelled_at, "total_price": "70.00", "current_total_price": total, "current_subtotal_price": "55.00",
            "current_total_discounts": "5.00", "current_total_tax": "4.00",
            "refunds": refunds if refunds is not None else [],
            "shipping_lines": [{"price": "5.00"}], "shipping_address": {"city": "Lahore", "province_code": "PB"},
            "line_items": [
                {"id": 1001, "product_id": 201, "variant_id": 301, "title": "Shopify Jacket", "sku": "SKU-1", "quantity": 2, "price": "25.00", "total_discount": "5.00"},
                {"id": 1002, "product_id": None, "variant_id": None, "title": "Unknown add-on", "sku": None, "quantity": 1, "price": "10.00", "total_discount": "0.00"},
            ]}


def test_shopify_client_pagination_validates_link_and_reuses_token(monkeypatch):
    calls = []
    page_two = "https://demo.myshopify.com/admin/api/2026-04/products.json?page_info=abc&limit=250"

    class Response:
        status_code = 200
        headers = {}
        def __init__(self, body, links=None):
            self._body, self.links = body, links or {}
        def json(self):
            return self._body

    responses = [Response({"products": [{"id": 1}]}, {"next": {"url": page_two}}), Response({"products": [{"id": 2}]})]
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return responses.pop(0)

    client = ShopifyClient("demo.myshopify.com", "sentinel-token", get=get, sleep=lambda _: None)
    assert [row["id"] for row in client.get_pages("products", {"limit": 250})] == [1, 2]
    assert calls[0][1]["headers"]["X-Shopify-Access-Token"] == "sentinel-token"
    assert calls[1][1]["params"] is None
    assert calls[1][1]["allow_redirects"] is False
    bad = ShopifyClient("demo.myshopify.com", "sentinel-token", get=lambda *_a, **_k: Response({"products": []}, {"next": {"url": "https://attacker.example/admin/api/2026-04/products.json"}}))
    with pytest.raises(ShopifyAPIError, match="pagination"):
        bad.get_pages("products")
    versioned = ShopifyClient("demo.myshopify.com", "x", api_version="2026-07", get=lambda *a, **k: Response({"shop": {}}))
    assert "/2026-07/shop.json" in versioned._url("shop")
    with pytest.raises(ValueError):
        ShopifyClient("demo.myshopify.com", "x", api_version="latest")


def test_shopify_client_retries_transient_and_redacts_permanent_failures():
    class Response:
        headers = {"Retry-After": "0.1"}
        def __init__(self, status): self.status_code = status
        def json(self): return {"shop": {"name": "ok"}}
    sequence = iter([Response(429), Response(200)])
    calls, sleeps = [], []
    client = ShopifyClient("demo.myshopify.com", "very-secret", get=lambda *a, **k: calls.append(k) or next(sequence), sleep=sleeps.append)
    assert client.get_json("shop")["shop"]["name"] == "ok"
    assert len(calls) == 2 and sleeps == [0.1]
    fail = ShopifyClient("demo.myshopify.com", "very-secret", get=lambda *_a, **_k: Response(401), sleep=lambda _: None)
    with pytest.raises(ShopifyAPIError) as exc:
        fail.get_json("shop")
    assert exc.value.category == "authentication_failed"
    assert "very-secret" not in str(exc.value)


def test_product_sync_upserts_by_variant_and_preserves_norfae_costs(api_client, monkeypatch):
    owner = register(api_client, "shop-product@example.com")
    configure_shopify(api_client, owner)
    business_id = owner.json()["business"]["id"]
    with tenant_scope(business_id):
        with api_client.session_factory() as db:
            db.add(InventoryProduct(sku="SKU-1", product_name="Local name", product_cost=7.5, stock_quantity=2))
            db.add(Product(name="Local name", sku="SKU-1", buying_price=7.5, selling_price=10, stock=2))
            db.commit()
    monkeypatch.setattr(ShopifySyncService, "_fetch", staticmethod(lambda _db, _business, resource, _cursor: [product_payload()] if resource == "products" else []))
    first = api_client.post("/shopify/sync/products", headers=headers(owner))
    assert first.status_code == 200, first.text
    assert first.json()["records_updated"] == 1
    with tenant_scope(business_id):
        with api_client.session_factory() as db:
            inv = db.query(InventoryProduct).one()
            prod = db.query(Product).one()
            assert inv.shopify_variant_id == "301" and inv.shopify_sku == "SKU-1"
            assert inv.product_cost == 7.5 and inv.selling_price == 25 and inv.stock_quantity == 8
            assert prod.buying_price == 7.5 and prod.shopify_description == "Imported description"
            assert prod.shopify_image_url == "https://cdn.shopify.com/s/files/jacket.jpg"
    second = api_client.post("/shopify/sync/products", headers=headers(owner))
    assert second.status_code == 200, second.text
    with tenant_scope(business_id):
        with api_client.session_factory() as db:
            assert db.query(InventoryProduct).count() == 1
            assert db.query(Product).count() == 1


def test_product_sync_handles_duplicate_skus_without_identity_collision(api_client, monkeypatch):
    owner = register(api_client, "shop-duplicate-sku@example.com")
    configure_shopify(api_client, owner)
    first, second = product_payload(variant_id="301"), product_payload(variant_id="302")
    second["variants"][0]["sku"] = "SKU-1"
    monkeypatch.setattr(ShopifySyncService, "_fetch", staticmethod(lambda *_args: [first, second]))
    response = api_client.post("/shopify/sync/products", headers=headers(owner))
    assert response.status_code == 200, response.text
    business_id = owner.json()["business"]["id"]
    with tenant_scope(business_id):
        with api_client.session_factory() as db:
            rows = db.query(InventoryProduct).order_by(InventoryProduct.shopify_variant_id).all()
            assert len(rows) == 2
            assert {row.shopify_variant_id for row in rows} == {"301", "302"}
            assert rows[1].sku is None and rows[1].shopify_sku == "SKU-1"


def test_order_sync_imports_lines_idempotently_updates_cancellation_and_omits_pii(api_client, monkeypatch):
    owner = register(api_client, "shop-order@example.com")
    configure_shopify(api_client, owner)
    business_id = owner.json()["business"]["id"]
    with tenant_scope(business_id):
        with api_client.session_factory() as db:
            db.add(InventoryProduct(shopify_product_id="201", shopify_variant_id="301", sku="SKU-1", product_name="Jacket", product_cost=8))
            db.commit()
    records = [order_payload()]
    monkeypatch.setattr(ShopifySyncService, "_fetch", staticmethod(lambda *_args: records))
    first = api_client.post("/shopify/sync/orders", headers=headers(owner))
    assert first.status_code == 200, first.text
    second = api_client.post("/shopify/sync/orders", headers=headers(owner))
    assert second.status_code == 200, second.text
    with tenant_scope(business_id):
        with api_client.session_factory() as db:
            order = db.query(Order).one()
            items = db.query(OrderItem).order_by(OrderItem.shopify_line_item_id).all()
            assert order.shopify_order_id == "901" and order.city == "Lahore"
            assert order.source == "shopify" and order.status == "PROCESSING"
            assert order.customer_name is None and order.customer_phone is None and order.address is None
            assert order.shopify_shipping_price == 5 and order.shopify_total_discounts == 5
            assert order.shopify_original_total_price == 70 and order.shopify_total_price == 60
            assert len(items) == 2 and items[1].inventory_product_id is None
            assert items[0].unit_cost == 8 and items[0].shopify_discount == 5
            assert db.query(ShopifySyncState).one().orders_cursor is not None
    records[0] = order_payload(fulfillment="fulfilled", financial_status="partially_refunded",
                               total="50.00",
                               refunds=[{"transactions": [{"kind": "refund", "status": "success", "amount": "10.00"}]}])
    update = api_client.post("/shopify/sync/orders", headers=headers(owner))
    assert update.status_code == 200, update.text
    with tenant_scope(business_id):
        with api_client.session_factory() as db:
            order = db.query(Order).one()
            assert order.status == "PARTIALLY_REFUNDED"
            assert order.shopify_order_name == "#1001" and order.shopify_total_refunded == 10
            assert order.selling_price == 50
            result = DeterministicProfitabilityService.order_record(order)
            assert result.revenue.amount == 0
            assert result.refunds.amount is None
            assert db.query(OrderItem).count() == 2
    records[0] = order_payload(fulfillment="fulfilled", cancelled_at="2026-11-20T13:00:00Z")
    cancelled = api_client.post("/shopify/sync/orders", headers=headers(owner))
    assert cancelled.status_code == 200
    with tenant_scope(business_id):
        with api_client.session_factory() as db:
            assert db.query(Order).one().status == "CANCELLED"


def test_provider_failure_keeps_cursor_and_records_failed_run(api_client, monkeypatch):
    owner = register(api_client, "shop-failure@example.com")
    configure_shopify(api_client, owner)
    monkeypatch.setattr(ShopifySyncService, "_fetch", staticmethod(lambda *_args: (_ for _ in ()).throw(ShopifyAPIError("authentication_failed", "Safe authentication error"))))
    response = api_client.post("/shopify/sync/products", headers=headers(owner))
    assert response.status_code == 502
    assert "Safe authentication error" in response.text
    assert "test-shopify-token" not in response.text
    business_id = owner.json()["business"]["id"]
    with tenant_scope(business_id):
        with api_client.session_factory() as db:
            assert db.query(ShopifySyncState).one().products_cursor is None


def test_order_rows_and_completion_status_share_one_transaction(api_client, monkeypatch):
    owner = register(api_client, "shop-atomic-failure@example.com")
    configure_shopify(api_client, owner)
    monkeypatch.setattr(ShopifySyncService, "_fetch", staticmethod(lambda *_args: [order_payload()]))
    fired = {"value": False}
    with tenant_scope(owner.json()["business"]["id"]):
        with api_client.session_factory() as db:
            def fail_order_commit(session):
                completing_run = any(isinstance(row, ShopifySyncRun) and row.sync_type == "orders" and row.status == "completed" for row in session.dirty)
                if completing_run and not fired["value"]:
                    fired["value"] = True
                    raise RuntimeError("simulated commit failure")

            event.listen(db, "before_commit", fail_order_commit)
            try:
                result = ShopifySyncService.sync_orders(db, owner.json()["business"]["id"], owner.json()["user"]["id"])
            finally:
                event.remove(db, "before_commit", fail_order_commit)
            assert result["status"] == "failed"
            assert db.query(Order).count() == 0
            assert db.query(OrderItem).count() == 0


def test_sync_endpoints_require_membership_and_history_is_business_scoped(api_client):
    owner = register(api_client, "shop-access-owner@example.com")
    other = register(api_client, "shop-access-other@example.com")
    denied = api_client.post("/shopify/sync/products", headers={"Authorization": headers(owner)["Authorization"], "X-Business-ID": headers(other)["X-Business-ID"]})
    assert denied.status_code == 404
    history = api_client.get("/shopify/sync/history", headers=headers(other))
    assert history.status_code == 200 and history.json() == []
    unauthenticated = api_client.post("/shopify/sync/products")
    assert unauthenticated.status_code == 401


def test_viewer_cannot_start_shopify_sync(api_client):
    owner = register(api_client, "shop-permission-owner@example.com")
    viewer = register(api_client, "shop-permission-viewer@example.com")
    business_id = owner.json()["business"]["id"]
    added = api_client.post(f"/businesses/{business_id}/memberships",
                            headers=headers(owner), json={"email": "shop-permission-viewer@example.com", "role": "viewer"})
    assert added.status_code == 201
    denied = api_client.post("/shopify/sync/products", headers={
        "Authorization": headers(viewer)["Authorization"], "X-Business-ID": str(business_id),
    })
    assert denied.status_code == 403


def test_businesses_use_their_own_shopify_store_and_token(api_client, monkeypatch):
    a = register(api_client, "shop-credential-a@example.com")
    b = register(api_client, "shop-credential-b@example.com")
    configure_shopify(api_client, a, "store-a.myshopify.com", "token-a")
    configure_shopify(api_client, b, "store-b.myshopify.com", "token-b")
    observed = []
    monkeypatch.setattr(ShopifyClient, "get_pages", lambda client, resource, params: observed.append((client.origin, client._token)) or [])
    assert api_client.post("/shopify/sync/products", headers=headers(a)).status_code == 200
    assert api_client.post("/shopify/sync/products", headers=headers(b)).status_code == 200
    assert observed == [("https://store-a.myshopify.com", "token-a"), ("https://store-b.myshopify.com", "token-b")]


def test_store_switch_after_completed_sync_is_rejected(api_client, monkeypatch):
    owner = register(api_client, "shop-store-switch@example.com")
    configure_shopify(api_client, owner, "old-store.myshopify.com", "old-token")
    monkeypatch.setattr(ShopifyClient, "get_pages", lambda *_args, **_kwargs: [])
    first = api_client.post("/shopify/sync/products", headers=headers(owner))
    assert first.status_code == 200
    switched = api_client.put("/settings/integrations", headers=headers(owner), json={"shopify_store_url": "new-store.myshopify.com", "shopify_access_token": "new-token"})
    assert switched.status_code == 409
    rejected = api_client.post("/shopify/sync/products", headers=headers(owner))
    assert rejected.status_code == 200


def test_store_cannot_change_while_sync_lease_is_active(api_client):
    owner = register(api_client, "shop-store-running@example.com")
    configure_shopify(api_client, owner)
    with api_client.session_factory() as db:
        with tenant_scope(owner.json()["business"]["id"]):
            state = ShopifySyncState(business_id=owner.json()["business"]["id"])
            db.add(state)
            state.products_running_since = datetime.utcnow()
            db.commit()
    switched = api_client.put("/settings/integrations", headers=headers(owner), json={"shopify_store_url": "new-store.myshopify.com"})
    assert switched.status_code == 409


def test_full_sync_returns_validated_aggregate_and_history(api_client, monkeypatch):
    owner = register(api_client, "shop-full@example.com")
    configure_shopify(api_client, owner)
    monkeypatch.setattr(ShopifySyncService, "_fetch", staticmethod(
        lambda _db, _business, resource, _cursor: [product_payload()] if resource == "products" else [order_payload()]
    ))
    result = api_client.post("/shopify/sync", headers=headers(owner))
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["status"] == "completed"
    assert body["run"]["sync_type"] == "full" and body["run"]["trigger_type"] == "manual"
    assert body["run"]["records_created"] == 2
    history = api_client.get("/shopify/sync/history", headers=headers(owner))
    assert history.status_code == 200
    assert {entry["sync_type"] for entry in history.json()} == {"full", "products", "orders"}
