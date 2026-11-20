import pytest

from app.core.tokens import TokenConfigurationError
from app.models import Business, BusinessMembership, MembershipRole, User


def register(client, email="owner@example.com", business_name="Norfae test"):
    return client.post(
        "/auth/register",
        json={
            "full_name": "Test Owner",
            "email": email,
            "password": "correct-horse-battery-staple",
            "business_name": business_name,
        },
    )


def bearer(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_registration_creates_user_business_and_owner_membership_atomically(api_client):
    response = register(api_client, " OWNER@Example.com ")

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "owner@example.com"
    assert "password_hash" not in body["user"]
    assert "password_hash" not in body
    assert body["business"]["owner_id"] == body["user"]["id"]

    with api_client.session_factory() as db:
        user = db.query(User).one()
        business = db.query(Business).one()
        membership = db.query(BusinessMembership).one()
        assert user.password_hash != "correct-horse-battery-staple"
        assert membership.user_id == user.id
        assert membership.business_id == business.id
        assert membership.role == MembershipRole.OWNER
        assert membership.is_active


def test_registration_duplicate_email_and_password_validation(api_client):
    assert register(api_client).status_code == 201
    duplicate = register(api_client, "OWNER@example.com", "another business")
    invalid_password = api_client.post(
        "/auth/register",
        json={
            "email": "new@example.com",
            "password": "short",
            "business_name": "No business",
        },
    )
    invalid_email = api_client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "correct-horse-battery-staple", "business_name": "No business"},
    )

    assert duplicate.status_code == 409
    assert invalid_password.status_code == 422
    assert invalid_email.status_code == 422
    assert "short-secret" not in invalid_password.text
    with api_client.session_factory() as db:
        assert db.query(User).count() == 1
        assert db.query(Business).count() == 1
        assert db.query(BusinessMembership).count() == 1


def test_registration_rolls_back_every_record_if_token_creation_fails(
    api_client, monkeypatch
):
    import app.routers.auth as auth_router_module

    def fail_token(_user_id):
        raise TokenConfigurationError("test")

    monkeypatch.setattr(auth_router_module, "create_access_token", fail_token)
    response = register(api_client)

    assert response.status_code == 503
    with api_client.session_factory() as db:
        assert db.query(User).count() == 0
        assert db.query(Business).count() == 0
        assert db.query(BusinessMembership).count() == 0


def test_login_current_user_and_inactive_account(api_client):
    registration = register(api_client)
    assert registration.status_code == 201
    login = api_client.post(
        "/auth/login",
        json={"email": "OWNER@example.com", "password": "correct-horse-battery-staple"},
    )
    wrong_password = api_client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "incorrect-password-value"},
    )
    unknown_email = api_client.post(
        "/auth/login",
        json={"email": "unknown@example.com", "password": "correct-horse-battery-staple"},
    )
    current = api_client.get("/auth/me", headers=bearer(login))
    missing = api_client.get("/auth/me")

    assert login.status_code == 200
    assert login.json()["business"]["id"] == registration.json()["business"]["id"]
    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert unknown_email.json()["detail"] == wrong_password.json()["detail"]
    assert current.status_code == 200
    assert current.json()["email"] == "owner@example.com"
    assert "password_hash" not in current.json()
    assert missing.status_code == 401

    with api_client.session_factory() as db:
        inactive = User(
            email="inactive@example.com",
            password_hash="not-a-real-login-hash",
            is_active=False,
        )
        db.add(inactive)
        db.commit()
    inactive_login = api_client.post(
        "/auth/login",
        json={"email": "inactive@example.com", "password": "correct-horse-battery-staple"},
    )
    assert inactive_login.status_code == 401


def test_registration_and_business_creation_return_accessible_memberships(api_client):
    owner = register(api_client)
    created = api_client.post(
        "/businesses",
        json={"name": "Second business"},
        headers=bearer(owner),
    )
    businesses = api_client.get("/businesses", headers=bearer(owner))

    assert created.status_code == 201
    assert businesses.status_code == 200
    assert {item["role"] for item in businesses.json()} == {"owner"}
    assert len(businesses.json()) == 2


def test_owner_business_membership_mismatch_fails_closed(api_client):
    owner = register(api_client)
    business_id = owner.json()["business"]["id"]
    with api_client.session_factory() as db:
        membership = db.query(BusinessMembership).one()
        membership.role = MembershipRole.ANALYST
        db.commit()

    response = api_client.get(f"/businesses/{business_id}", headers=bearer(owner))
    assert response.status_code == 403
    assert "ownership membership is inconsistent" in response.json()["detail"]


def test_membership_addition_is_by_existing_email_and_scoped(api_client):
    owner = register(api_client, "owner@example.com", "Owner business")
    other_user = register(api_client, "member@example.com", "Their own business")
    business_id = owner.json()["business"]["id"]

    cross_business = api_client.get(
        f"/businesses/{business_id}", headers=bearer(other_user)
    )
    added = api_client.post(
        f"/businesses/{business_id}/memberships",
        json={"email": "MEMBER@example.com", "role": "viewer"},
        headers=bearer(owner),
    )
    duplicate = api_client.post(
        f"/businesses/{business_id}/memberships",
        json={"email": "member@example.com", "role": "analyst"},
        headers=bearer(owner),
    )
    now_member = api_client.get(
        f"/businesses/{business_id}", headers=bearer(other_user)
    )

    assert cross_business.status_code == 404
    assert added.status_code == 201
    assert added.json()["role"] == "viewer"
    assert duplicate.status_code == 409
    assert now_member.status_code == 200


@pytest.mark.parametrize("role", ["analyst", "viewer"])
def test_analyst_and_viewer_cannot_manage_business_or_members(api_client, role):
    owner = register(api_client)
    member = register(api_client, "member@example.com", "Member business")
    business_id = owner.json()["business"]["id"]
    assert api_client.post(
        f"/businesses/{business_id}/memberships",
        json={"email": "member@example.com", "role": role},
        headers=bearer(owner),
    ).status_code == 201

    update_business = api_client.patch(
        f"/businesses/{business_id}",
        json={"name": "Unauthorized change"},
        headers=bearer(member),
    )
    manage_members = api_client.get(
        f"/businesses/{business_id}/memberships", headers=bearer(member)
    )

    assert update_business.status_code == 403
    assert manage_members.status_code == 403


def test_admin_cannot_grant_admin_or_change_owner_but_owner_can_manage_members(
    api_client,
):
    owner = register(api_client)
    admin = register(api_client, "admin@example.com", "Admin business")
    business_id = owner.json()["business"]["id"]
    assert api_client.post(
        f"/businesses/{business_id}/memberships",
        json={"email": "admin@example.com", "role": "admin"},
        headers=bearer(owner),
    ).status_code == 201

    admin_grant = api_client.post(
        f"/businesses/{business_id}/memberships",
        json={"email": "owner@example.com", "role": "admin"},
        headers=bearer(admin),
    )
    admin_owner_change = api_client.patch(
        f"/businesses/{business_id}/memberships/{owner.json()['user']['id']}",
        json={"is_active": False},
        headers=bearer(admin),
    )
    owner_update = api_client.patch(
        f"/businesses/{business_id}",
        json={"name": "Owner updated name"},
        headers=bearer(owner),
    )

    assert admin_grant.status_code == 403
    assert admin_owner_change.status_code == 409
    assert owner_update.status_code == 200


def test_inactive_membership_and_owner_removal_are_rejected(api_client):
    owner = register(api_client)
    member = register(api_client, "member@example.com", "Member business")
    business_id = owner.json()["business"]["id"]
    api_client.post(
        f"/businesses/{business_id}/memberships",
        json={"email": "member@example.com", "role": "analyst"},
        headers=bearer(owner),
    )
    owner_id = owner.json()["user"]["id"]
    disable_owner = api_client.patch(
        f"/businesses/{business_id}/memberships/{owner_id}",
        json={"is_active": False},
        headers=bearer(owner),
    )
    remove_owner = api_client.delete(
        f"/businesses/{business_id}/memberships/{owner_id}",
        headers=bearer(owner),
    )
    disable_member = api_client.patch(
        f"/businesses/{business_id}/memberships/{member.json()['user']['id']}",
        json={"is_active": False},
        headers=bearer(owner),
    )
    inactive_access = api_client.get(
        f"/businesses/{business_id}", headers=bearer(member)
    )

    assert disable_owner.status_code == 409
    assert remove_owner.status_code == 409
    assert disable_member.status_code == 200
    assert inactive_access.status_code == 404
