from fastapi import FastAPI


def test_application_imports_and_registers_routes(application):
    assert isinstance(application, FastAPI)
    assert application.title == "Norfae Intelligence OS"

    paths = {route.path for route in application.routes if hasattr(route, "path")}
    assert "/health" in paths
    assert "/docs" in paths
    assert "/ws/dashboard" in paths


def test_openapi_endpoint_is_valid_and_contains_existing_api_paths(api_get):
    response = api_get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"]

    paths = schema["paths"]
    for path in (
        "/orders/",
        "/products/",
        "/expenses/",
        "/meta-ads/overview",
        "/dashboard/overview",
        "/intelligence/data-quality",
        "/intelligence/profitability",
        "/intelligence/profitability/products",
        "/intelligence/profitability/orders/{order_id}",
        "/intelligence/products",
        "/intelligence/products/{product_id}",
        "/intelligence/cities",
        "/intelligence/cities/{city_name}",
        "/intelligence/marketing/overview",
        "/intelligence/marketing/campaigns",
        "/intelligence/marketing/campaigns/{campaign_id}",
        "/intelligence/marketing/trends",
        "/intelligence/creatives",
        "/intelligence/creatives/comparison",
        "/intelligence/creatives/{creative_id}",
    ):
        assert path in paths
