import pytest
from fastapi import WebSocketDisconnect


def register(client, email="owner@example.com"):
    return client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "business_name": "Test business",
        },
    )


def tenant_headers(response):
    return {
        "Authorization": f"Bearer {response.json()['access_token']}",
        "X-Business-ID": str(response.json()["business"]["id"]),
    }


def test_public_app_routes_and_openapi_remain_available(api_client):
    assert api_client.get("/").status_code == 200
    assert api_client.get("/health").json() == {"status": "healthy"}
    assert api_client.get("/docs").status_code == 200

    openapi_response = api_client.get("/openapi.json")
    assert openapi_response.status_code == 200
    paths = openapi_response.json()["paths"]
    assert "/auth/register" in paths
    assert "/auth/login" in paths
    assert "/auth/me" in paths
    assert "/businesses/{business_id}/memberships" in paths
    assert "/orders/" in paths
    auth = paths["/auth/me"]["get"]
    assert auth["security"] == [{"HTTPBearer": []}]
    assert "HTTPBearer" in openapi_response.json()["components"]["securitySchemes"]
    assert "201" in paths["/auth/register"]["post"]["responses"]
    assert "200" in paths["/auth/login"]["post"]["responses"]


def test_legacy_data_route_requires_business_context_and_is_restored(api_client):
    owner = register(api_client)
    without_context = api_client.get("/orders/", headers={
        "Authorization": tenant_headers(owner)["Authorization"]
    })
    scoped = api_client.get("/orders/", headers=tenant_headers(owner))

    assert without_context.status_code == 422
    assert scoped.status_code == 200


def test_system_status_requires_authentication(api_client):
    assert api_client.get("/system/status").status_code == 401


@pytest.mark.parametrize(
    "path", ["/ws/dashboard", "/ws/orders", "/ws/notifications"]
)
def test_unscoped_websockets_close_before_accept(api_client, path):
    with pytest.raises(WebSocketDisconnect) as disconnected:
        with api_client.websocket_connect(path):
            pytest.fail("Unscoped websocket should not accept a connection.")
    assert disconnected.value.code == 1008
