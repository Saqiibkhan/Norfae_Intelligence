from datetime import date, datetime, timedelta

from app.core.tenant_context import tenant_scope
from app.models import MetaAdInsight, MetaSyncRun, MetaSyncState
from app.services.meta_client import MetaAPIError, MetaClient
from app.services.meta_insights_sync_service import MetaInsightsSyncService, MetaSyncError


def register(client, email):
    return client.post("/auth/register", json={
        "email": email, "password": "correct-horse-battery-staple",
        "business_name": email.split("@")[0],
    })


def headers(auth):
    return {
        "Authorization": f"Bearer {auth.json()['access_token']}",
        "X-Business-ID": str(auth.json()["business"]["id"]),
    }


def configure_meta(client, auth, account_id="act_12345", token="meta-test-token"):
    result = client.put("/settings/integrations", headers=headers(auth), json={
        "meta_account_id": account_id, "meta_access_token": token,
    })
    assert result.status_code == 200, result.text


class Response:
    def __init__(self, body, status=200, headers=None):
        self._body = body
        self.status_code = status
        self.headers = headers or {}
        self.is_redirect = 300 <= status < 400

    def json(self):
        return self._body


def test_meta_client_uses_bearer_token_validates_pagination_and_retries():
    requests_seen = []
    responses = [
        Response({"data": [{"id": "act_12345", "name": "Demo"}],
                  "paging": {"next": "https://graph.facebook.com/v27.0/me/adaccounts?after=x&access_token=leaked"}}),
        Response({"data": [{"id": "act_67890", "name": "Second"}]}),
    ]

    def get(url, **kwargs):
        requests_seen.append((url, kwargs))
        return responses.pop(0)

    client = MetaClient("meta-test-token", get=get, sleep=lambda _: None)
    assert [row["id"] for row in client.list_accounts()] == ["act_12345", "act_67890"]
    assert requests_seen[0][1]["headers"]["Authorization"] == "Bearer meta-test-token"
    assert "meta-test-token" not in requests_seen[0][0]
    assert "access_token" not in requests_seen[1][0]
    assert requests_seen[0][1]["allow_redirects"] is False
    assert requests_seen[0][1]["timeout"] == (5, 25)

    bad = MetaClient("x", get=lambda *_a, **_k: Response({"data": [], "paging": {
        "next": "https://attacker.example/v27.0/me/adaccounts"
    }}))
    try:
        bad.list_accounts()
    except MetaAPIError as error:
        assert error.category == "invalid_pagination"
    else:
        raise AssertionError("untrusted pagination link was accepted")


def test_meta_client_retries_rate_limit_and_redacts_provider_errors():
    calls = []
    sequence = [Response({"error": {"message": "token meta-test-token", "code": 4}}, 400),
                Response({"data": []})]
    client = MetaClient("meta-test-token", get=lambda *_a, **_k: calls.append(1) or sequence.pop(0), sleep=lambda _: None)
    assert client.list_accounts() == []
    assert len(calls) == 2

    fail = MetaClient("meta-test-token", get=lambda *_a, **_k: Response(
        {"error": {"message": "token meta-test-token", "code": 190}}, 400), sleep=lambda _: None)
    try:
        fail.list_accounts()
    except MetaAPIError as error:
        assert error.category == "provider_error"
        assert "meta-test-token" not in str(error)
    else:
        raise AssertionError("provider error was not raised")


def _mock_meta(monkeypatch):
    monkeypatch.setattr(MetaClient, "get_account", lambda self, account_id: {
        "id": f"act_{account_id}", "currency": "PKR", "timezone_name": "Asia/Karachi",
    })

    def get_insights(self, account_id, level, start_date, end_date):
        id_key = {"account": "account_id", "campaign": "campaign_id", "adset": "adset_id", "ad": "ad_id"}[level]
        row = {
            id_key: f"act_{account_id}" if level == "account" else f"{level}-1",
            "account_id": f"act_{account_id}", "account_currency": "PKR",
            "date_start": start_date, "date_stop": end_date,
            "spend": "120.50", "impressions": "2000", "reach": "1500", "clicks": "100",
            "inline_link_clicks": "40", "ctr": "5", "cpc": "1.205", "cpm": "60.25",
            "frequency": "1.3", "actions": [{"action_type": "purchase", "value": "2"}],
            "action_values": [{"action_type": "purchase", "value": "500.00"}],
            "cost_per_action_type": [{"action_type": "purchase", "value": "60.25"}],
        }
        if level != "account":
            row[f"{level}_name"] = f"{level.title()} Name"
            row["campaign_id"] = "campaign-1"
            row["campaign_name"] = "Campaign One"
            if level in {"adset", "ad"}:
                row.update(adset_id="adset-1", adset_name="Adset One")
            if level == "ad":
                row.update(ad_id="ad-1", ad_name="Ad One")
        rows = []
        day = date.fromisoformat(start_date)
        last_day = date.fromisoformat(end_date)
        while day <= last_day:
            daily = dict(row)
            daily["date_start"] = day.isoformat()
            daily["date_stop"] = day.isoformat()
            rows.append(daily)
            day += timedelta(days=1)
        return rows

    monkeypatch.setattr(MetaClient, "get_insights", get_insights)


def test_meta_sync_is_tenant_scoped_idempotent_and_preserves_platform_actions(api_client, monkeypatch):
    owner = register(api_client, "meta-sync-owner@example.com")
    other = register(api_client, "meta-sync-other@example.com")
    configure_meta(api_client, owner)
    configure_meta(api_client, other, "act_67890", "other-meta-token")
    _mock_meta(monkeypatch)

    payload = {"start_date": "2026-10-01", "end_date": "2026-10-01"}
    first = api_client.post("/meta-ads/sync/insights", headers=headers(owner), json=payload)
    second = api_client.post("/meta-ads/sync/insights", headers=headers(owner), json=payload)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["run"]["records_created"] == 4
    assert second.json()["run"]["records_updated"] == 4
    assert first.json()["run"]["account_id"] == "12345"

    insights = api_client.get("/meta-ads/insights?level=ad", headers=headers(owner))
    assert insights.status_code == 200
    assert len(insights.json()) == 1
    assert insights.json()[0]["currency"] == "PKR"
    assert insights.json()[0]["actions"] == [{"action_type": "purchase", "value": "2"}]
    assert insights.json()[0]["action_values"] == [{"action_type": "purchase", "value": "500.00"}]
    assert insights.json()[0]["action_attribution_windows"] == ["default"]
    assert insights.json()[0]["action_report_time"] == "mixed"

    history_owner = api_client.get("/meta-ads/syncs/history", headers=headers(owner))
    history_other = api_client.get("/meta-ads/syncs/history", headers=headers(other))
    assert history_owner.status_code == 200 and len(history_owner.json()) == 2
    assert history_other.status_code == 200 and history_other.json() == []
    other_campaigns = api_client.get("/meta-ads/campaigns", headers=headers(other))
    assert other_campaigns.status_code == 200 and other_campaigns.json()["campaigns"] == []
    assert api_client.get("/meta-ads/overview").status_code in {401, 403}
    with tenant_scope(other.json()["business"]["id"]), api_client.session_factory() as db:
        assert db.query(MetaAdInsight).all() == []
        assert db.query(MetaSyncRun).all() == []


def test_meta_sync_reports_partial_records_and_does_not_hide_failed_pages(api_client, monkeypatch):
    owner = register(api_client, "meta-sync-partial@example.com")
    configure_meta(api_client, owner)
    _mock_meta(monkeypatch)
    original = MetaClient.get_insights

    def partial(client, account_id, level, start_date, end_date):
        rows = original(client, account_id, level, start_date, end_date)
        if level == "adset":
            rows[0].pop("adset_id")
        return rows

    monkeypatch.setattr(MetaClient, "get_insights", partial)
    body = {"start_date": "2026-10-01", "end_date": "2026-10-01"}
    result = api_client.post("/meta-ads/sync/insights", headers=headers(owner), json=body)
    assert result.status_code == 200
    assert result.json()["status"] == "partially_completed"
    assert result.json()["run"]["records_skipped"] == 1

    monkeypatch.setattr(MetaClient, "get_insights", lambda *_args: (_ for _ in ()).throw(MetaAPIError("rate_limited", "Meta rate limited the request.")))
    failed = api_client.post("/meta-ads/sync/insights", headers=headers(owner), json=body)
    assert failed.status_code == 502
    assert failed.json()["status"] == "failed"
    assert "meta-test-token" not in failed.text

    def fail_campaign_page(_client, _account, level, _start, _end):
        if level == "campaign":
            raise MetaAPIError("pagination_limit", "Meta pagination exceeded the configured page limit.")
        return original(_client, _account, level, _start, _end)

    monkeypatch.setattr(MetaClient, "get_insights", fail_campaign_page)
    partial_page = api_client.post("/meta-ads/sync/insights", headers=headers(owner), json=body)
    assert partial_page.status_code == 200, partial_page.text
    assert partial_page.json()["status"] == "partially_completed"
    assert partial_page.json()["run"]["error_category"] == "pagination_limit"


def test_meta_account_switch_is_locked_after_sync_and_validation_is_strict(api_client, monkeypatch):
    owner = register(api_client, "meta-account-lock@example.com")
    configure_meta(api_client, owner)
    _mock_meta(monkeypatch)
    response = api_client.post("/meta-ads/sync/insights", headers=headers(owner), json={
        "start_date": "2026-10-01", "end_date": "2026-10-01",
    })
    assert response.status_code == 200
    switched = api_client.put("/settings/integrations", headers=headers(owner), json={"meta_account_id": "99999"})
    assert switched.status_code == 409
    bad = api_client.put("/settings/integrations", headers=headers(owner), json={"meta_account_id": "not-an-account"})
    assert bad.status_code == 422


def test_meta_campaign_reporting_aggregates_daily_rows_without_summing_reach(api_client, monkeypatch):
    owner = register(api_client, "meta-aggregate@example.com")
    configure_meta(api_client, owner)
    _mock_meta(monkeypatch)
    synced = api_client.post("/meta-ads/sync/insights", headers=headers(owner), json={
        "start_date": "2026-10-01", "end_date": "2026-10-02",
    })
    assert synced.status_code == 200, synced.text
    campaigns = api_client.get(
        "/meta-ads/campaigns?start_date=2026-10-01&end_date=2026-10-02",
        headers=headers(owner),
    )
    assert campaigns.status_code == 200
    assert len(campaigns.json()["campaigns"]) == 1
    campaign = campaigns.json()["campaigns"][0]
    assert campaign["spend"] == 241.0
    assert campaign["impressions"] == 4000
    assert campaign["clicks"] == 200
    assert campaign["reach"] is None
    assert campaign["sales"] == 4


def test_expired_meta_run_cannot_clear_a_newer_run_lease(api_client, monkeypatch):
    owner = register(api_client, "meta-lease@example.com")
    configure_meta(api_client, owner)
    _mock_meta(monkeypatch)
    synced = api_client.post("/meta-ads/sync/insights", headers=headers(owner), json={
        "start_date": "2026-10-01", "end_date": "2026-10-01",
    })
    assert synced.status_code == 200
    business_id = owner.json()["business"]["id"]
    original_run_id = synced.json()["run"]["run_id"]
    newer_lease_id = original_run_id + 100
    running_since = datetime.utcnow() - timedelta(hours=2)
    with tenant_scope(business_id), api_client.session_factory() as db:
        state = db.query(MetaSyncState).first()
        run = db.query(MetaSyncRun).filter(MetaSyncRun.id == original_run_id).first()
        state.active_run_id = newer_lease_id
        state.running_since = running_since
        run.status = "running"
        db.commit()
        result = MetaInsightsSyncService._finish(
            db, business_id, original_run_id, status="completed",
            counts={"fetched": 4, "created": 4, "updated": 0, "skipped": 0},
            error=MetaSyncError("lease_expired", "Old run expired."),
        )
        assert result["status"] == "failed"
        assert state.active_run_id == newer_lease_id
        assert state.running_since == running_since
