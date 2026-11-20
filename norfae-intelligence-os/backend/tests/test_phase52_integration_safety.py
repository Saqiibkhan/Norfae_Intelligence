import asyncio
import importlib
from types import SimpleNamespace

import pytest
import requests
from pydantic import ValidationError

from app.schemas.settings_schema import SettingsIntegrationUpdate
from app.services import shopify_service
from app.services.shopify_service import ShopifyService
from app.utils.shopify_url import normalize_shopify_store_url


def bearer(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def business_header(response):
    return {"X-Business-ID": str(response.json()["business"]["id"])}


def register(client, email):
    return client.post(
        "/auth/register",
        json={"email": email, "password": "correct-horse-battery-staple", "business_name": email},
    )


def test_meta_task_module_and_package_import_without_starting_scheduler():
    module = importlib.import_module("app.tasks.sync_meta_ads")
    package = importlib.import_module("app.tasks")
    assert package.MetaAdsSyncTask is module.MetaAdsSyncTask

    scheduler_module = importlib.import_module("app.services.scheduler_service")
    assert scheduler_module.scheduler.running is False


def test_meta_sync_once_success_and_missing_configuration(monkeypatch):
    from app.tasks.sync_meta_ads import MetaAdsSyncTask

    class FakeDB:
        def __init__(self):
            self.closed = False

        def query(self, model):
            return self

        def filter(self, *args):
            return self

        def first(self):
            return object()

        def close(self):
            self.closed = True

    dbs = []

    def session():
        db = FakeDB()
        dbs.append(db)
        return db

    monkeypatch.setattr("app.tasks.sync_meta_ads.SessionLocal", session)
    monkeypatch.setattr(
        "app.tasks.sync_meta_ads.MetaSyncService.sync_today_stats",
        lambda _db: {"success": True, "data": {"spend": 12}},
    )
    assert MetaAdsSyncTask.sync_once(7) == {"success": True}
    assert all(db.closed for db in dbs)

    monkeypatch.setattr(
        "app.tasks.sync_meta_ads.MetaSyncService.sync_today_stats",
        lambda _db: {"success": False, "message": "Meta credentials missing"},
    )
    assert MetaAdsSyncTask.sync_once(7) == {
        "success": False,
        "error_code": "configuration_missing",
    }


def test_meta_sync_once_controls_service_failures(monkeypatch, caplog):
    from app.tasks.sync_meta_ads import MetaAdsSyncTask

    class FakeDB:
        def query(self, _model):
            return self

        def filter(self, *_args):
            return self

        def first(self):
            return object()

        def close(self):
            pass

    monkeypatch.setattr("app.tasks.sync_meta_ads.SessionLocal", FakeDB)

    def fail(_db):
        raise RuntimeError("provider-private-secret")

    monkeypatch.setattr("app.tasks.sync_meta_ads.MetaSyncService.sync_today_stats", fail)
    assert MetaAdsSyncTask.sync_once(7) == {"success": False, "error_code": "sync_failed"}
    assert "provider-private-secret" not in caplog.text


@pytest.mark.parametrize(
    "value",
    [
        "evil.example",
        "https://evil.example",
        "http://store.myshopify.com",
        "localhost",
        "127.0.0.1",
        "https://10.0.0.1",
        "https://store.myshopify.com:8443",
        "https://store.myshopify.com/path",
        "https://user:pass@store.myshopify.com",
        "not a url",
    ],
)
def test_shopify_store_url_rejects_untrusted_hosts_and_shapes(value):
    with pytest.raises(ValueError):
        normalize_shopify_store_url(value)


def test_shopify_store_url_normalizes_supported_domain():
    assert normalize_shopify_store_url("My-Store.myshopify.com") == "https://my-store.myshopify.com"
    assert normalize_shopify_store_url("https://my-store.myshopify.com:443/") == "https://my-store.myshopify.com"
    assert SettingsIntegrationUpdate(shopify_store_url="my-store.myshopify.com").shopify_store_url == "https://my-store.myshopify.com"


def _fake_db(settings_row):
    class Query:
        def filter(self, *_args):
            return self

        def first(self):
            return settings_row

    class DB:
        def query(self, _model):
            return Query()

    return DB()


def _settings(url="demo.myshopify.com", token="shopify-private-token"):
    return SimpleNamespace(shopify_store_url=url, shopify_access_token=token)


def test_shopify_status_uses_normalized_host_timeout_and_disables_redirects(monkeypatch):
    calls = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"shop": {"name": "Demo store"}}

    monkeypatch.setattr(shopify_service.requests, "get", lambda *args, **kwargs: calls.append((args, kwargs)) or Response())
    result = ShopifyService.service_status(_fake_db(_settings()), 10)
    assert result["connected"] is True
    assert calls[0][0][0] == "https://demo.myshopify.com/admin/api/2026-04/shop.json"
    assert calls[0][1]["timeout"] == shopify_service.SHOPIFY_STATUS_TIMEOUT_SECONDS
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["headers"]["X-Shopify-Access-Token"] == "shopify-private-token"


@pytest.mark.parametrize(
    "error,expected",
    [
        (requests.Timeout("shopify-private-token timeout"), "Shopify status request timed out."),
        (requests.ConnectionError("shopify-private-token at internal host"), "Shopify status request could not connect."),
    ],
)
def test_shopify_status_handles_network_errors_without_leaking_credentials(monkeypatch, caplog, error, expected):
    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(shopify_service.requests, "get", fail)
    result = ShopifyService.service_status(_fake_db(_settings()), 10)
    assert result["message"] == expected
    assert "shopify-private-token" not in str(result)
    assert "shopify-private-token" not in caplog.text


def test_shopify_status_rejects_redirect_provider_error_and_bad_json(monkeypatch):
    class Response:
        def __init__(self, status, body=None):
            self.status_code = status
            self.body = body

        def json(self):
            if isinstance(self.body, Exception):
                raise self.body
            return self.body

    responses = iter((Response(302), Response(500, {"token": "provider-secret"}), Response(200, ValueError("bad"))))
    monkeypatch.setattr(shopify_service.requests, "get", lambda *_args, **_kwargs: next(responses))
    for expected in (
        "Shopify redirected the status request; redirects are not followed.",
        "Shopify status request failed.",
        "Shopify returned an invalid response.",
    ):
        result = ShopifyService.service_status(_fake_db(_settings()), 10)
        assert result["connected"] is False
        assert result["message"] == expected
        assert "provider-secret" not in str(result)


def test_shopify_status_rejects_legacy_invalid_url_before_sending_token(monkeypatch):
    calls = []
    monkeypatch.setattr(shopify_service.requests, "get", lambda *args, **kwargs: calls.append(args))
    result = ShopifyService.service_status(_fake_db(_settings("https://attacker.example")), 10)
    assert result["connected"] is False
    assert calls == []


def test_shopify_status_uses_authenticated_business_credentials(api_client, monkeypatch):
    owner_a = register(api_client, "shopify-a@example.com")
    owner_b = register(api_client, "shopify-b@example.com")
    for owner, store, token in (
        (owner_a, "store-a.myshopify.com", "token-business-a"),
        (owner_b, "store-b.myshopify.com", "token-business-b"),
    ):
        response = api_client.put(
            "/settings/integrations",
            json={"shopify_store_url": store, "shopify_access_token": token},
            headers={**bearer(owner), **business_header(owner)},
        )
        assert response.status_code == 200

    captured = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"shop": {"name": "Store A"}}

    monkeypatch.setattr(
        shopify_service.requests,
        "get",
        lambda url, **kwargs: captured.append((url, kwargs["headers"]["X-Shopify-Access-Token"])) or Response(),
    )
    result = api_client.get("/shopify/status", headers={**bearer(owner_a), **business_header(owner_a)})
    assert result.status_code == 200
    assert captured == [("https://store-a.myshopify.com/admin/api/2026-04/shop.json", "token-business-a")]
    assert "token-business-b" not in result.text
