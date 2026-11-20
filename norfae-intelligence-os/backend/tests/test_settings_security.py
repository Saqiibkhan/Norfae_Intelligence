from app.models import BusinessMembership, MembershipRole, SettingsModel, User
from app.core.tokens import create_access_token
from app.core.tenant_context import tenant_scope


def bearer(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def business_header(response):
    return {"X-Business-ID": str(response.json()["business"]["id"])}


def register(client, email="owner@example.com", business_name="Norfae test"):
    return client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "business_name": business_name,
        },
    )


def test_settings_requires_auth_and_never_returns_tokens(api_client):
    owner = register(api_client)
    with tenant_scope(owner.json()["business"]["id"]):
        with api_client.session_factory() as db:
            row = SettingsModel(
                shopify_access_token="shopify-private-sentinel",
                meta_access_token="meta-private-sentinel",
            )
            db.add(row)
            db.commit()

    unauthorized = api_client.get("/settings/", headers=business_header(owner))
    response = api_client.get(
        "/settings/", headers={**bearer(owner), **business_header(owner)}
    )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert "shopify_access_token" not in response.json()
    assert "meta_access_token" not in response.json()
    assert response.json()["shopify_connected"] is True
    assert response.json()["meta_connected"] is True
    assert "shopify-private-sentinel" not in response.text
    assert "meta-private-sentinel" not in response.text


def test_integration_secret_omissions_preserve_credentials_and_clear_is_explicit(
    api_client, caplog
):
    owner = register(api_client)
    with tenant_scope(owner.json()["business"]["id"]):
        with api_client.session_factory() as db:
            row = SettingsModel(
                shopify_access_token="old-shopify-secret",
                meta_access_token="old-meta-secret",
            )
            db.add(row)
            db.commit()

    replacement = "new-shopify-secret-value"
    response = api_client.put(
        "/settings/integrations",
        json={"shopify_access_token": replacement},
        headers={**bearer(owner), **business_header(owner)},
    )
    assert response.status_code == 200
    assert replacement not in response.text
    assert "old-meta-secret" not in response.text
    assert "meta_access_token" not in response.json()["settings"]

    with tenant_scope(owner.json()["business"]["id"]):
        with api_client.session_factory() as db:
            row = db.query(SettingsModel).one()
            assert row.shopify_access_token == replacement
            assert row.meta_access_token == "old-meta-secret"

    cleared = api_client.put(
        "/settings/integrations",
        json={"clear_meta_access_token": True},
        headers={**bearer(owner), **business_header(owner)},
    )
    assert cleared.status_code == 200
    assert cleared.json()["settings"]["meta_connected"] is False
    with tenant_scope(owner.json()["business"]["id"]):
        with api_client.session_factory() as db:
            row = db.query(SettingsModel).one()
            assert row.shopify_access_token == replacement
            assert row.meta_access_token is None

    assert replacement not in caplog.text
    assert "old-meta-secret" not in caplog.text


def test_null_secret_is_not_an_implicit_clear_and_legacy_write_is_rejected(api_client):
    owner = register(api_client)
    with tenant_scope(owner.json()["business"]["id"]):
        with api_client.session_factory() as db:
            db.add(SettingsModel(shopify_access_token="preserved-secret"))
            db.commit()

    null_secret = api_client.put(
        "/settings/integrations",
        json={"shopify_access_token": None},
        headers={**bearer(owner), **business_header(owner)},
    )
    legacy_write = api_client.post(
        "/settings/",
        json={"shopify_access_token": "do-not-store"},
        headers={**bearer(owner), **business_header(owner)},
    )

    assert null_secret.status_code == 422
    assert legacy_write.status_code == 422
    with tenant_scope(owner.json()["business"]["id"]):
        with api_client.session_factory() as db:
            assert db.query(SettingsModel).one().shopify_access_token == "preserved-secret"


def test_admin_cannot_modify_shared_integration_credentials(api_client):
    owner = register(api_client)
    with api_client.session_factory() as db:
        owner_row = db.query(User).filter_by(email="owner@example.com").one()
        admin = User(email="admin@example.com", password_hash="test-hash")
        db.add(admin)
        db.flush()
        initial_business = db.query(BusinessMembership).filter_by(user_id=owner_row.id).one().business
        db.add(
            BusinessMembership(
                user=admin,
                business=initial_business,
                role=MembershipRole.ADMIN,
                is_active=True,
            )
        )
        db.commit()
        admin_id = admin.id

    with tenant_scope(owner.json()["business"]["id"]):
        with api_client.session_factory() as db:
            db.add(SettingsModel(shopify_access_token="existing-secret"))
            db.commit()

    admin_token = create_access_token(admin_id)
    response = api_client.put(
        "/settings/integrations",
        json={"shopify_access_token": "unauthorized-secret"},
        headers={"Authorization": f"Bearer {admin_token}", **business_header(owner)},
    )

    assert response.status_code == 403
    with tenant_scope(owner.json()["business"]["id"]):
        with api_client.session_factory() as db:
            assert db.query(SettingsModel).one().shopify_access_token == "existing-secret"


def test_settings_are_isolated_per_business(api_client):
    owner = register(api_client)
    second = register(api_client, "second@example.com", "Second business")

    first_write = api_client.post(
        "/settings/",
        json={"gst_percentage": 9},
        headers={**bearer(owner), **business_header(owner)},
    )
    second_write = api_client.post(
        "/settings/",
        json={"gst_percentage": 18},
        headers={**bearer(second), **business_header(second)},
    )
    first_read = api_client.get(
        "/settings/", headers={**bearer(owner), **business_header(owner)}
    )
    second_read = api_client.get(
        "/settings/", headers={**bearer(second), **business_header(second)}
    )

    assert first_write.status_code == 200
    assert second_write.status_code == 200
    assert first_read.json()["gst_percentage"] == 9
    assert second_read.json()["gst_percentage"] == 18


