"""Read-only, host-pinned Shopify Admin REST client."""

import time
import re
from urllib.parse import parse_qsl, urlsplit

import requests

from app.core.config import settings
from app.utils.shopify_url import normalize_shopify_store_url

SHOPIFY_API_VERSION = "2026-04"
SHOPIFY_TIMEOUT = (3.05, 20)
MAX_ATTEMPTS = 3
MAX_PAGES = 1000


class ShopifyAPIError(Exception):
    def __init__(self, category: str, safe_summary: str, *, retryable: bool = False):
        super().__init__(safe_summary)
        self.category = category
        self.safe_summary = safe_summary
        self.retryable = retryable


class ShopifyClient:
    def __init__(self, store_url: str, access_token: str, *, get=None, sleep=time.sleep, timeout=SHOPIFY_TIMEOUT, api_version=None):
        self.origin = normalize_shopify_store_url(store_url)
        if not isinstance(access_token, str) or not access_token.strip():
            raise ShopifyAPIError("configuration_missing", "Shopify access token is missing.")
        self._token = access_token
        self._get = get or requests.get
        self._sleep = sleep
        self._timeout = timeout
        self.api_version = api_version or settings.SHOPIFY_API_VERSION
        if not re.fullmatch(r"20\d{2}-(01|04|07|10)", self.api_version):
            raise ValueError("Unsupported Shopify API version format.")
        self._host = urlsplit(self.origin).hostname

    def _url(self, resource: str) -> str:
        if resource not in {"shop", "products", "orders"}:
            raise ShopifyAPIError("invalid_request", "Unsupported Shopify resource.")
        return f"{self.origin}/admin/api/{self.api_version}/{resource}.json"

    def _validate_next_url(self, url: str, expected_path: str) -> None:
        try:
            parsed = urlsplit(url)
            valid = (
                parsed.scheme == "https" and parsed.hostname == self._host
                and parsed.port in (None, 443) and parsed.username is None
                and parsed.password is None and parsed.path == expected_path
                and not parsed.fragment
                and all(key in {"page_info", "limit", "fields"} for key, _ in parse_qsl(parsed.query, keep_blank_values=True))
            )
        except ValueError:
            valid = False
        if not valid:
            raise ShopifyAPIError("pagination_error", "Shopify returned an invalid pagination link.")

    def get_json(self, resource: str, params: dict | None = None) -> dict:
        response = self._request(self._url(resource), params=params)
        try:
            body = response.json()
        except (ValueError, requests.RequestException):
            raise ShopifyAPIError("invalid_response", "Shopify returned invalid JSON.") from None
        if not isinstance(body, dict):
            raise ShopifyAPIError("invalid_response", "Shopify returned an invalid response.")
        return body

    def get_pages(self, resource: str, params: dict | None = None) -> list[dict]:
        url = self._url(resource)
        result = []
        for _page_number in range(MAX_PAGES):
            response = self._request(url, params=params)
            try:
                body = response.json()
            except (ValueError, requests.RequestException):
                raise ShopifyAPIError("invalid_response", "Shopify returned invalid JSON.") from None
            collection = body.get(resource) if isinstance(body, dict) else None
            if not isinstance(collection, list) or any(not isinstance(item, dict) for item in collection):
                raise ShopifyAPIError("invalid_response", "Shopify returned an invalid resource collection.")
            result.extend(collection)
            next_url = getattr(response, "links", {}).get("next", {}).get("url")
            if not next_url:
                return result
            expected_path = f"/admin/api/{self.api_version}/{resource}.json"
            self._validate_next_url(next_url, expected_path)
            url, params = next_url, None
        raise ShopifyAPIError("pagination_limit", "Shopify pagination exceeded the safety limit.")

    def _request(self, url: str, *, params: dict | None = None):
        headers = {"X-Shopify-Access-Token": self._token, "Accept": "application/json"}
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = self._get(
                    url, headers=headers, params=params, timeout=self._timeout,
                    allow_redirects=False,
                )
            except requests.Timeout:
                if attempt + 1 < MAX_ATTEMPTS:
                    self._sleep(0.25 * (2 ** attempt))
                    continue
                raise ShopifyAPIError("timeout", "Shopify request timed out.", retryable=True) from None
            except requests.ConnectionError:
                if attempt + 1 < MAX_ATTEMPTS:
                    self._sleep(0.25 * (2 ** attempt))
                    continue
                raise ShopifyAPIError("network_error", "Shopify could not be reached.", retryable=True) from None
            except requests.RequestException:
                raise ShopifyAPIError("request_error", "Shopify request failed.") from None

            status = response.status_code
            if status == 200:
                self._respect_rate_header(response)
                return response
            if 300 <= status < 400:
                raise ShopifyAPIError("redirect_rejected", "Shopify redirected the request; redirects are disabled.")
            if status in (401, 403):
                raise ShopifyAPIError("authentication_failed", "Shopify rejected the configured credentials or permissions.")
            if status == 404:
                raise ShopifyAPIError("store_not_found", "Shopify store or resource was not found.")
            if status == 429 or status in (500, 502, 503, 504):
                if attempt + 1 < MAX_ATTEMPTS:
                    delay = 0.5
                    if status == 429:
                        try:
                            delay = min(max(float(response.headers.get("Retry-After", 1)), 0.1), 5.0)
                        except (TypeError, ValueError):
                            delay = 1.0
                    self._sleep(delay)
                    continue
                category = "rate_limited" if status == 429 else "provider_unavailable"
                message = "Shopify rate limit retries were exhausted." if status == 429 else "Shopify is temporarily unavailable."
                raise ShopifyAPIError(category, message, retryable=True)
            if 400 <= status < 500:
                raise ShopifyAPIError("invalid_request", "Shopify rejected the synchronization request.")
            raise ShopifyAPIError("provider_error", "Shopify returned an unexpected response.")
        raise ShopifyAPIError("provider_unavailable", "Shopify retries were exhausted.", retryable=True)

    def _respect_rate_header(self, response) -> None:
        try:
            used, capacity = response.headers.get("X-Shopify-Shop-Api-Call-Limit", "").split("/", 1)
            if int(used) >= max(1, int(capacity) - 3):
                self._sleep(0.5)
        except (ValueError, TypeError, AttributeError):
            return
