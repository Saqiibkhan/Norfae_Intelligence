from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from datetime import datetime, timedelta

from app.core.database import get_db

from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/orders", tags=["Analytics"])

# ===================================
# ORDER ANALYTICS
# ===================================


@router.get("/analytics")
def get_order_analytics(
    start_date: str = None, end_date: str = None, db: Session = Depends(get_db)
):

    try:

        # ===============================
        # DEFAULT
        # ===============================

        start = None

        end = None

        # ===============================
        # DATE FILTER
        # ===============================

        if start_date and end_date:

            start = datetime.strptime(start_date, "%Y-%m-%d")

            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        # ===============================
        # ANALYTICS
        # ===============================

        analytics = AnalyticsService.get_order_analytics(
            db=db, start_date=start, end_date=end
        )

        return {
            "success": True,
            "date_range": {"start_date": start_date, "end_date": end_date},
            "summary": analytics,
        }

    except Exception as e:

        return {"success": False, "message": str(e)}


# ===================================
# ORDER TRENDS
# ===================================


@router.get("/analytics/trends")
def get_order_trends(
    start_date: str = None, end_date: str = None, db: Session = Depends(get_db)
):

    try:

        # ===============================
        # DEFAULT
        # ===============================

        start = None

        end = None

        # ===============================
        # DATE FILTER
        # ===============================

        if start_date and end_date:

            start = datetime.strptime(start_date, "%Y-%m-%d")

            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        # ===============================
        # TRENDS
        # ===============================

        trends = AnalyticsService.get_order_trends(
            db=db, start_date=start, end_date=end
        )

        return {"success": True, "trends": trends}

    except Exception as e:

        return {"success": False, "message": str(e)}


# ===================================
# COMPARATIVE ANALYTICS
# ===================================


@router.get("/analytics/comparison")
def get_analytics_comparison(
    start_date: str = None, end_date: str = None, db: Session = Depends(get_db)
):

    try:

        # ===============================
        # ALL TIME
        # ===============================

        if not start_date or not end_date:

            comparison = AnalyticsService.get_comparative_analytics(
                db=db,
                current_start=None,
                current_end=None,
                previous_start=None,
                previous_end=None,
            )

            return {"success": True, "comparison": comparison}

        # ===============================
        # CURRENT PERIOD
        # ===============================

        current_start = datetime.strptime(start_date, "%Y-%m-%d")

        current_end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        # ===============================
        # PREVIOUS PERIOD
        # ===============================

        delta = current_end - current_start

        previous_end = current_start

        previous_start = previous_end - delta

        # ===============================
        # COMPARISON
        # ===============================

        comparison = AnalyticsService.get_comparative_analytics(
            db=db,
            current_start=current_start,
            current_end=current_end,
            previous_start=previous_start,
            previous_end=previous_end,
        )

        return {"success": True, "comparison": comparison}

    except Exception as e:

        return {"success": False, "message": str(e)}
