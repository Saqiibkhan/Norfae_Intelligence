from __future__ import annotations

import time
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from app.core.config import settings


META_API_BASE = "https://graph.facebook.com"
META_TIMEOUT = (5, 25)
META_MAX_RETRIES = 3
META_MAX_PAGES = 500
TRANSIENT_GRAPH_CODES = {4, 17, 32, 613}


class MetaAPIError(Exception):
    def __init__(self, category: str, safe_summary: str):
        super().__init__(safe_summary)
        self.category = category
        self.safe_summary = safe_summary


class MetaClient:
    """Read-only Meta Marketing API client with bounded, validated paging."""

    def __init__(self, access_token: str, *, api_version: str | None = None,
                 get=None, sleep=time.sleep):
        if not isinstance(access_token, str) or not access_token.strip():
            raise ValueError("A Meta access token is required.")
        self._token = access_token.strip()
        self.api_version = api_version or settings.META_API_VERSION
        if not isinstance(self.api_version, str) or not re.fullmatch(r"v\d{1,2}\.0", self.api_version):
            raise ValueError("Meta API version is invalid.")
        self._get = get or requests.get
        self._sleep = sleep
        self.root = f"{META_API_BASE}/{self.api_version}"

    @staticmethod
    def normalize_account_id(value: str) -> str:
        account_id = value.strip() if isinstance(value, str) else ""
        if account_id.startswith("act_"):
            account_id = account_id[4:]
        if not account_id.isdigit() or len(account_id) > 32:
            raise ValueError("Meta ad account ID must contain digits, optionally prefixed by act_.")
        return account_id

    def list_accounts(self) -> list[dict]:
        return self._get_pages("me/adaccounts", {
            "fields": "id,name,account_status,currency,timezone_name",
            "limit": 100,
        })

    def get_account(self, account_id: str) -> dict:
        normalized = self.normalize_account_id(account_id)
        payload = self._request_json(
            f"{self.root}/act_{normalized}",
            {"fields": "id,name,account_status,currency,timezone_name"},
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            raise MetaAPIError("invalid_response", "Meta returned an invalid ad account response.")
        return payload

    def get_insights(self, account_id: str, level: str, start_date: str, end_date: str) -> list[dict]:
        normalized = self.normalize_account_id(account_id)
        level_fields = {
            "account": ("account_id,account_name,account_currency", f"act_{normalized}"),
            "campaign": ("account_id,account_currency,campaign_id,campaign_name", f"act_{normalized}"),
            "adset": ("account_id,account_currency,campaign_id,campaign_name,adset_id,adset_name", f"act_{normalized}"),
            "ad": ("account_id,account_currency,campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name", f"act_{normalized}"),
        }
        if level not in level_fields:
            raise ValueError("Meta insight level must be account, campaign, adset, or ad.")
        dimensions, node = level_fields[level]
        fields = ",".join((dimensions, "date_start,date_stop,spend,impressions,reach,clicks,inline_link_clicks,ctr,cpc,cpm,frequency,actions,action_values,cost_per_action_type"))
        return self._get_pages(f"{node}/insights", {
            "fields": fields,
            "level": level,
            "time_increment": 1,
            "time_range": json.dumps({"since": start_date, "until": end_date}, separators=(",", ":")),
            "action_attribution_windows": json.dumps(["default"], separators=(",", ":")),
            "action_report_time": "mixed",
            "limit": 500,
        })

    def _request_json(self, url: str, params: dict | None = None):
        for attempt in range(META_MAX_RETRIES + 1):
            try:
                response = self._get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
                    timeout=META_TIMEOUT,
                    allow_redirects=False,
                )
            except requests.Timeout:
                if attempt < META_MAX_RETRIES:
                    self._sleep(min(0.5 * (2 ** attempt), 4))
                    continue
                raise MetaAPIError("timeout", "Meta request timed out.") from None
            except requests.RequestException:
                if attempt < META_MAX_RETRIES:
                    self._sleep(min(0.5 * (2 ** attempt), 4))
                    continue
                raise MetaAPIError("network_error", "Meta request could not connect.") from None

            if response.is_redirect:
                raise MetaAPIError("redirect_rejected", "Meta returned an unexpected redirect.")
            retry_after = response.headers.get("Retry-After") if hasattr(response, "headers") else None
            try:
                payload = response.json()
            except (ValueError, requests.JSONDecodeError):
                payload = None
            graph_error = payload.get("error") if isinstance(payload, dict) else None
            graph_code = graph_error.get("code") if isinstance(graph_error, dict) else None
            retryable = response.status_code in {429, 500, 502, 503, 504} or graph_code in TRANSIENT_GRAPH_CODES
            if retryable and attempt < META_MAX_RETRIES:
                delay = _retry_delay(retry_after, attempt)
                self._sleep(delay)
                continue
            if response.status_code >= 400 or graph_error:
                category = "rate_limited" if response.status_code == 429 or graph_code in TRANSIENT_GRAPH_CODES else "provider_error"
                summary = "Meta rate limited the request." if category == "rate_limited" else "Meta rejected the request or returned an API error."
                raise MetaAPIError(category, summary)
            if not isinstance(payload, dict):
                raise MetaAPIError("invalid_response", "Meta returned an invalid response.")
            return payload
        raise MetaAPIError("provider_error", "Meta request failed.")

    def _get_pages(self, path: str, params: dict) -> list[dict]:
        url = f"{self.root}/{path}"
        page_params = dict(params)
        rows: list[dict] = []
        for _ in range(META_MAX_PAGES):
            payload = self._request_json(url, page_params)
            data = payload.get("data")
            if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
                raise MetaAPIError("invalid_response", "Meta returned an invalid data page.")
            rows.extend(data)
            paging = payload.get("paging") or {}
            if not isinstance(paging, dict):
                raise MetaAPIError("invalid_response", "Meta returned invalid pagination metadata.")
            next_url = paging.get("next")
            if not next_url:
                return rows
            url = self._validate_next_url(next_url)
            page_params = None
        raise MetaAPIError("pagination_limit", "Meta pagination exceeded the configured page limit.")

    def _validate_next_url(self, value: str) -> str:
        if not isinstance(value, str) or len(value) > 8192:
            raise MetaAPIError("invalid_pagination", "Meta returned an invalid pagination link.")
        try:
            parsed = urlsplit(value)
            if (parsed.scheme != "https" or parsed.hostname != "graph.facebook.com"
                    or parsed.port not in (None, 443) or parsed.username or parsed.password
                    or parsed.fragment or not parsed.path.startswith(f"/{self.api_version}/")):
                raise ValueError
            pairs = [(key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True)
                     if key.casefold() != "access_token"]
            return urlunsplit(("https", "graph.facebook.com", parsed.path, urlencode(pairs), ""))
        except (TypeError, ValueError):
            raise MetaAPIError("invalid_pagination", "Meta returned an invalid pagination link.") from None


def _retry_delay(retry_after, attempt: int) -> float:
    try:
        value = float(retry_after)
        if value >= 0:
            return min(value, 10.0)
    except (TypeError, ValueError):
        pass
    return min(0.5 * (2 ** attempt), 4.0)
