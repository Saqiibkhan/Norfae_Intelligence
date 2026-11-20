from typing import Optional

from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from app.core.database import get_db

from app.services.meta_ads_service import MetaAdsService

from app.services.meta_sync_service import MetaSyncService

from app.services.meta_expense_service import (
    MetaExpenseService,
)

router = APIRouter(prefix="/meta-ads", tags=["Meta Ads"])

# ===================================
# META OVERVIEW
# ===================================


@router.get("/overview")
def get_meta_overview(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
):

    print("META OVERVIEW")
    print("START DATE =", start_date)
    print("END DATE =", end_date)

    return MetaAdsService.get_account_overview(db, start_date, end_date)


# ===================================
# META SYNC
# ===================================


@router.post("/sync")
def sync_meta_data(db: Session = Depends(get_db)):

    return MetaSyncService.sync_today_stats(db)


@router.post("/sync-history")
def sync_meta_history(
    start_date: str = "2026-01-01",
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
):

    result = MetaSyncService.sync_historical_stats(
        db,
        start_date,
        end_date,
    )

    MetaExpenseService.sync_historical_expenses(db)

    return result

    return MetaSyncService.sync_historical_stats(
        db,
        start_date,
        end_date,
    )


# ===================================
# TODAY STATS
# ===================================


@router.get("/today")
def get_today_stats(db: Session = Depends(get_db)):

    return MetaAdsService.get_today_stats(db)


# ===================================
# ANALYSIS
# ===================================


@router.get("/analysis")
def get_analysis(db: Session = Depends(get_db)):

    return MetaAdsService.get_analysis(db)


# ===================================
# CAMPAIGNS
# ===================================


@router.get("/campaigns")
def get_campaigns(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
):

    return MetaAdsService.get_campaigns(db, start_date, end_date)


# ===================================
# ADSETS
# ===================================


@router.get("/adsets")
def get_adsets(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
):

    return MetaAdsService.get_adsets(db, start_date, end_date)


# ===================================
# ADS
# ===================================


@router.get("/ads")
def get_ads(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
):

    return MetaAdsService.get_ads(db, start_date, end_date)
