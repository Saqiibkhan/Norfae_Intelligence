from datetime import date
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.authorization import get_business_context
from app.core.database import get_db
from app.schemas.meta_ads_schema import (
    MetaAccount, MetaAccountsResponse, MetaHistoryEntry, MetaStatusResponse,
    MetaSyncRequest, MetaSyncResponse,
)
from app.services.meta_ads_service import MetaAdsService
from app.services.meta_client import MetaAPIError, MetaClient
from app.services.meta_insights_sync_service import MetaInsightsSyncService, MetaSyncError
from app.core.timezone import pakistan_now

router = APIRouter(prefix="/meta-ads", tags=["Meta Ads"])


def _raise_meta_error(error: MetaSyncError):
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.category, "message": error.summary},
    ) from None


@router.get("/status", response_model=MetaStatusResponse)
def meta_status(membership=Depends(get_business_context), db: Session = Depends(get_db)):
    return MetaInsightsSyncService.status(db, membership.business_id)


@router.get("/accounts", response_model=MetaAccountsResponse)
def meta_accounts(membership=Depends(get_business_context), db: Session = Depends(get_db)):
    try:
        client = MetaInsightsSyncService.client_for_account_listing(db, membership.business_id)
        rows = client.list_accounts()
    except MetaSyncError as error:
        _raise_meta_error(error)
    except MetaAPIError as error:
        raise HTTPException(status_code=502, detail={"code": error.category, "message": error.safe_summary}) from None
    accounts = []
    for row in rows:
        try:
            account_id = str(row["id"])
            MetaClient.normalize_account_id(account_id)
            accounts.append(MetaAccount(
                id=account_id, name=row.get("name"), account_status=row.get("account_status"),
                currency=row.get("currency"), timezone_name=row.get("timezone_name"),
            ))
        except (KeyError, ValueError, TypeError):
            continue
    return {"accounts": accounts}


@router.post("/sync/insights", response_model=MetaSyncResponse)
def sync_meta_insights(data: MetaSyncRequest, response: Response,
                       membership=Depends(get_business_context), db: Session = Depends(get_db)):
    try:
        result = MetaInsightsSyncService.sync(
            db, membership.business_id, membership.user_id, data.start_date, data.end_date,
        )
    except MetaSyncError as error:
        _raise_meta_error(error)
    if result["status"] == "failed":
        response.status_code = 502
    return result


@router.get("/syncs/history", response_model=list[MetaHistoryEntry])
def meta_sync_history(limit: int = Query(default=50, ge=1, le=100),
                      membership=Depends(get_business_context), db: Session = Depends(get_db)):
    return MetaInsightsSyncService.history(db, membership.business_id, limit)


@router.get("/insights")
def read_meta_insights(level: str = Query(default="campaign", pattern="^(account|campaign|adset|ad)$"),
                       start_date: date | None = None, end_date: date | None = None,
                       limit: int = Query(default=500, ge=1, le=2000),
                       membership=Depends(get_business_context), db: Session = Depends(get_db)):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    status = MetaInsightsSyncService.status(db, membership.business_id)
    account_id = status["selected_account_id"]
    if not account_id:
        raise HTTPException(status_code=409, detail={"code": "configuration_missing", "message": "A Meta ad account is not configured."})
    rows = MetaInsightsSyncService.insight_rows(db, membership.business_id, account_id, level, start_date, end_date)
    return [{
        "account_id": row.account_id, "currency": row.currency,
        "level": row.level, "entity_id": row.entity_id, "entity_name": row.entity_name,
        "campaign_id": row.campaign_id, "campaign_name": row.campaign_name,
        "adset_id": row.adset_id, "adset_name": row.adset_name,
        "ad_id": row.ad_id, "ad_name": row.ad_name,
        "date_start": row.date_start, "date_stop": row.date_stop,
        "spend": str(row.spend) if row.spend is not None else None,
        "impressions": row.impressions, "reach": row.reach, "clicks": row.clicks,
        "inline_link_clicks": row.inline_link_clicks,
        "ctr": str(row.ctr) if row.ctr is not None else None,
        "cpc": str(row.cpc) if row.cpc is not None else None,
        "cpm": str(row.cpm) if row.cpm is not None else None,
        "frequency": str(row.frequency) if row.frequency is not None else None,
        "actions": json.loads(row.actions_json) if row.actions_json else None,
        "action_values": json.loads(row.action_values_json) if row.action_values_json else None,
        "cost_per_action_type": json.loads(row.cost_per_action_type_json) if row.cost_per_action_type_json else None,
        "action_attribution_windows": json.loads(row.action_attribution_windows_json),
        "action_report_time": row.action_report_time,
    } for row in rows[:limit]]


@router.get("/overview")
def get_meta_overview(start_date: date | None = None, end_date: date | None = None,
                      membership=Depends(get_business_context), db: Session = Depends(get_db)):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    return MetaAdsService.get_account_overview(db, start_date, end_date)


@router.post("/sync", response_model=MetaSyncResponse)
def sync_meta_today(response: Response, membership=Depends(get_business_context), db: Session = Depends(get_db)):
    today = pakistan_now().date()
    try:
        result = MetaInsightsSyncService.sync(db, membership.business_id, membership.user_id, today, today)
    except MetaSyncError as error:
        _raise_meta_error(error)
    if result["status"] == "failed":
        response.status_code = 502
    return result


@router.post("/sync-history", response_model=MetaSyncResponse)
def sync_meta_history(response: Response, start_date: date = Query(...), end_date: date = Query(...),
                      membership=Depends(get_business_context), db: Session = Depends(get_db)):
    if start_date > end_date or (end_date - start_date).days > 91:
        raise HTTPException(status_code=422, detail="Meta sync range must be ordered and no longer than 92 days.")
    try:
        result = MetaInsightsSyncService.sync(db, membership.business_id, membership.user_id, start_date, end_date)
    except MetaSyncError as error:
        _raise_meta_error(error)
    if result["status"] == "failed":
        response.status_code = 502
    return result


@router.get("/today")
def get_today_stats(membership=Depends(get_business_context), db: Session = Depends(get_db)):
    return MetaAdsService.get_today_stats(db)


@router.get("/analysis")
def get_analysis(membership=Depends(get_business_context), db: Session = Depends(get_db)):
    return MetaAdsService.get_analysis(db)


@router.get("/campaigns")
def get_campaigns(start_date: date | None = None, end_date: date | None = None,
                 membership=Depends(get_business_context), db: Session = Depends(get_db)):
    return MetaAdsService.get_campaigns(db, start_date, end_date)


@router.get("/adsets")
def get_adsets(start_date: date | None = None, end_date: date | None = None,
               membership=Depends(get_business_context), db: Session = Depends(get_db)):
    return MetaAdsService.get_adsets(db, start_date, end_date)


@router.get("/ads")
def get_ads(start_date: date | None = None, end_date: date | None = None,
            membership=Depends(get_business_context), db: Session = Depends(get_db)):
    return MetaAdsService.get_ads(db, start_date, end_date)
