def test_health_returns_success_payload(api_get):
    response = api_get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
