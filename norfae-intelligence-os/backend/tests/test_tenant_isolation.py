import pytest
from datetime import date
from sqlalchemy.exc import IntegrityError

from app.core.database import TenantContextRequired
from app.core.tenant_context import tenant_scope
from app.models import (
    Category,
    Expense,
    InventoryProduct,
    MetaDailyStats,
    Order,
    OrderItem,
    Product,
    SettingsModel,
)


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


def test_expense_reads_and_deletes_are_business_scoped(api_client):
    owner_a = register(api_client, "tenant-a@example.com")
    owner_b = register(api_client, "tenant-b@example.com")
    headers_a, headers_b = headers(owner_a), headers(owner_b)

    created_a = api_client.post(
        "/expenses/",
        json={"title": "A private expense", "amount": 31.5},
        headers=headers_a,
    )
    created_b = api_client.post(
        "/expenses/",
        json={"title": "B private expense", "amount": 64.0},
        headers=headers_b,
    )
    assert created_a.status_code == created_b.status_code == 200

    expenses_a = api_client.get("/expenses/?filter_type=all", headers=headers_a)
    expenses_b = api_client.get("/expenses/?filter_type=all", headers=headers_b)
    assert [row["title"] for row in expenses_a.json()] == ["A private expense"]
    assert [row["title"] for row in expenses_b.json()] == ["B private expense"]

    foreign_delete = api_client.delete(
        f"/expenses/{created_a.json()['id']}", headers=headers_b
    )
    still_visible = api_client.get("/expenses/?filter_type=all", headers=headers_a)
    assert foreign_delete.json()["success"] is False
    assert len(still_visible.json()) == 1

    with tenant_scope(owner_a.json()["business"]["id"]):
        with api_client.session_factory() as db:
            row = db.query(Expense).one()
            assert row.business_id == owner_a.json()["business"]["id"]


def test_another_business_id_without_membership_is_rejected(api_client):
    owner_a = register(api_client, "selected-a@example.com")
    owner_b = register(api_client, "selected-b@example.com")
    forged = {
        "Authorization": f"Bearer {owner_a.json()['access_token']}",
        "X-Business-ID": str(owner_b.json()["business"]["id"]),
    }
    response = api_client.get("/expenses/?filter_type=all", headers=forged)
    assert response.status_code == 404


def test_viewer_reads_but_cannot_write_business_data(api_client):
    owner = register(api_client, "viewer-owner@example.com")
    viewer = register(api_client, "viewer-user@example.com")
    business_id = owner.json()["business"]["id"]
    added = api_client.post(
        f"/businesses/{business_id}/memberships",
        json={"email": "viewer-user@example.com", "role": "viewer"},
        headers=headers(owner),
    )
    assert added.status_code == 201

    read = api_client.get(
        "/expenses/?filter_type=all",
        headers={
            "Authorization": f"Bearer {viewer.json()['access_token']}",
            "X-Business-ID": str(business_id),
        },
    )
    write = api_client.post(
        "/expenses/",
        json={"title": "viewer cannot create", "amount": 5},
        headers={
            "Authorization": f"Bearer {viewer.json()['access_token']}",
            "X-Business-ID": str(business_id),
        },
    )
    assert read.status_code == 200
    assert write.status_code == 403


def test_tenant_data_session_refuses_unscoped_queries(api_client):
    with api_client.session_factory() as db:
        with pytest.raises(TenantContextRequired):
            db.query(Expense).all()


def test_database_rejects_unassigned_settings_after_final_migration(api_client):
    owner = register(api_client, "settings-owner@example.com")
    engine = api_client.session_factory.kw["bind"]
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                SettingsModel.__table__.insert().values(business_id=None)
            )

    response = api_client.post(
        "/settings/",
        json={"gst_percentage": 16},
        headers=headers(owner),
    )
    assert response.status_code == 200
    with tenant_scope(owner.json()["business"]["id"]):
        with api_client.session_factory() as db:
            settings_row = db.query(SettingsModel).one()
            assert settings_row.business_id == owner.json()["business"]["id"]


def test_products_with_same_sku_are_isolated_between_businesses(api_client):
    owner_a = register(api_client, "products-a@example.com")
    owner_b = register(api_client, "products-b@example.com")
    payload = {
        "name": "Shared SKU name",
        "sku": "TENANT-SKU-1",
        "category": "Test",
        "size": "M",
        "website_size": "M",
        "weight_kg": 0.5,
        "buying_price": 10,
        "selling_price": 20,
        "stock": 3,
    }
    created_a = api_client.post("/products/", json=payload, headers=headers(owner_a))
    created_b = api_client.post("/products/", json=payload, headers=headers(owner_b))
    listed_a = api_client.get("/products/", headers=headers(owner_a))
    listed_b = api_client.get("/products/", headers=headers(owner_b))

    assert created_a.status_code == created_b.status_code == 200
    assert len(listed_a.json()) == len(listed_b.json()) == 1
    assert listed_a.json()[0]["sku"] == listed_b.json()[0]["sku"] == "TENANT-SKU-1"

    product_a_id = created_a.json()["product"]["id"]
    attempted_update = api_client.put(
        f"/products/{product_a_id}",
        json={"name": "cross-tenant overwrite"},
        headers=headers(owner_b),
    )
    attempted_delete = api_client.delete(
        f"/products/{product_a_id}", headers=headers(owner_b)
    )
    still_owned = api_client.get("/products/", headers=headers(owner_a))
    assert attempted_update.json()["error"] == "Product not found"
    assert attempted_delete.json()["error"] == "Product not found"
    assert still_owned.json()[0]["name"] == "Shared SKU name"

    with tenant_scope(owner_a.json()["business"]["id"]):
        with api_client.session_factory() as db:
            a = db.query(Product).one()
            assert a.business_id == owner_a.json()["business"]["id"]


def test_database_rejects_order_item_link_to_other_business_inventory(api_client):
    owner_a = register(api_client, "relationship-a@example.com")
    owner_b = register(api_client, "relationship-b@example.com")
    business_a = owner_a.json()["business"]["id"]
    business_b = owner_b.json()["business"]["id"]

    with tenant_scope(business_b):
        with api_client.session_factory() as db:
            inventory = InventoryProduct(
                product_name="B inventory",
                normalized_name="b inventory",
                sku="B-1",
            )
            db.add(inventory)
            db.commit()
            foreign_inventory_id = inventory.id

    with tenant_scope(business_a):
        with api_client.session_factory() as db:
            order = Order(internal_order_id="A-1", source="test")
            db.add(order)
            db.flush()
            item = OrderItem(
                order_id=order.id,
                inventory_product_id=foreign_inventory_id,
                product_name="wrong tenant",
            )
            db.add(item)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                rejected = True
            else:
                rejected = False

    assert rejected is True


def test_business_scoped_identifiers_allow_cross_tenant_reuse_only(api_client):
    owner_a = register(api_client, "unique-a@example.com")
    owner_b = register(api_client, "unique-b@example.com")
    business_ids = [
        owner_a.json()["business"]["id"],
        owner_b.json()["business"]["id"],
    ]
    cases = [
        (Product, {"name": "P", "sku": "same-sku"}),
        (
            InventoryProduct,
            {"product_name": "I", "normalized_name": "i", "sku": "same-sku"},
        ),
        (Order, {"internal_order_id": "same-order"}),
        (Expense, {"title": "E", "external_reference": "same-expense-ref"}),
        (Category, {"name": "Same category", "slug": "same-category"}),
        (MetaDailyStats, {"stats_date": date(2026, 1, 1)}),
    ]

    for model, values in cases:
        for business_id in business_ids:
            with tenant_scope(business_id):
                with api_client.session_factory() as db:
                    db.add(model(**values))
                    db.commit()

        with tenant_scope(business_ids[0]):
            with api_client.session_factory() as db:
                db.add(model(**values))
                with pytest.raises(IntegrityError):
                    db.commit()
                db.rollback()
