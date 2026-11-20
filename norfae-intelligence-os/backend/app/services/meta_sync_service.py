import json

import requests

from datetime import datetime

from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.settings_model import SettingsModel

from app.models.meta_daily_stats_model import MetaDailyStats


class MetaSyncService:

    @staticmethod
    def sync_today_stats(db: Session):

        # =========================================
        # SETTINGS
        # =========================================

        settings = db.query(SettingsModel).first()

        if not settings:
            return {"success": False, "message": "Settings not found"}

        access_token = settings.meta_access_token
        account_id = settings.meta_account_id

        if not access_token or not account_id:
            return {"success": False, "message": "Meta credentials missing"}

        account_id = account_id.replace("act_", "")

        # =========================================
        # TODAY DATE
        # =========================================

        today = datetime.now(ZoneInfo("Asia/Karachi")).date()

        # =========================================
        # CHECK EXISTING
        # =========================================

        existing = (
            db.query(MetaDailyStats).filter(MetaDailyStats.stats_date == today).first()
        )

        # =========================================
        # META API
        # =========================================

        url = f"https://graph.facebook.com/v25.0/act_{account_id}/insights"

        import json

        params = {
            "access_token": access_token,
            "fields": ",".join(
                [
                    "spend",
                    "impressions",
                    "reach",
                    "clicks",
                    "cpc",
                    "cpm",
                    "ctr",
                    "frequency",
                    "actions",
                    "cost_per_action_type",
                ]
            ),
            "date_preset": "today",
        }

        response = requests.get(
            url,
            params=params,
            timeout=30,
        )

        data = response.json()

        # =========================================
        # ERROR
        # =========================================

        if "error" in data:
            return {"success": False, "error": data["error"]}

        insights = data.get("data", [])

        if not insights:
            return {"success": False, "message": "No insights found"}

        insight = insights[0]

        actions = insight.get("actions", [])

        costs = insight.get("cost_per_action_type", [])

        # =========================================
        # HELPERS
        # =========================================

        def get_action_value(action_type):

            for action in actions:

                if action.get("action_type") == action_type:
                    return float(action.get("value", 0))

            return 0

        def get_cost_value(action_type):

            for item in costs:

                if item.get("action_type") == action_type:
                    return float(item.get("value", 0))

            return 0

        # =========================================
        # VALUES
        # =========================================

        instagram_messages = get_action_value(
            "onsite_conversion.messaging_conversation_started_7d"
        ) or get_action_value("onsite_conversion.total_messaging_connection")

        link_clicks = get_action_value("link_click")

        landing_page_views = get_action_value("landing_page_view")

        leads = get_action_value("lead")

        cost_per_instagram_message = get_cost_value(
            "onsite_conversion.messaging_conversation_started_7d"
        )

        # =========================================
        # CREATE OR UPDATE
        # =========================================

        if not existing:

            existing = MetaDailyStats(stats_date=today)

            db.add(existing)

        # =========================================
        # SAVE DATA
        # =========================================

        existing.spend = float(insight.get("spend", 0))

        existing.impressions = int(insight.get("impressions", 0))

        existing.clicks = int(insight.get("clicks", 0))

        existing.reach = int(insight.get("reach", 0))

        existing.cpc = float(insight.get("cpc", 0))

        existing.cpm = float(insight.get("cpm", 0))

        existing.ctr = float(insight.get("ctr", 0))

        existing.frequency = float(insight.get("frequency", 0))

        existing.instagram_messages = int(instagram_messages)

        existing.link_clicks = int(link_clicks)

        existing.landing_page_views = int(landing_page_views)

        existing.leads = int(leads)

        existing.cost_per_instagram_message = float(cost_per_instagram_message)

        # =========================================
        # SAVE
        # =========================================

        db.commit()

        db.refresh(existing)

        return {
            "success": True,
            "message": "Meta stats synced successfully",
            "data": {
                "date": str(existing.stats_date),
                "spend": existing.spend,
                "instagram_messages": existing.instagram_messages,
                "clicks": existing.clicks,
            },
        }

    @staticmethod
    def sync_historical_stats(
        db: Session,
        start_date: str = "2026-01-01",
        end_date: str = None,
    ):

        settings = db.query(SettingsModel).first()

        if not settings:
            return {"success": False, "message": "Settings not found"}

        access_token = settings.meta_access_token
        account_id = settings.meta_account_id

        if not access_token or not account_id:
            return {"success": False, "message": "Meta credentials missing"}

        account_id = account_id.replace("act_", "")

        if not end_date:
            end_date = datetime.now(ZoneInfo("Asia/Karachi")).strftime("%Y-%m-%d")

        url = f"https://graph.facebook.com/v25.0/act_{account_id}/insights"

        params = {
            "access_token": access_token,
            "fields": ",".join(
                [
                    "spend",
                    "impressions",
                    "reach",
                    "clicks",
                    "cpc",
                    "cpm",
                    "ctr",
                    "frequency",
                    "actions",
                    "cost_per_action_type",
                ]
            ),
            "time_increment": 1,
            "time_range": json.dumps(
                {
                    "since": start_date,
                    "until": end_date,
                }
            ),
        }

        print("===================================")
        print("META HISTORICAL REQUEST")
        print("START HISTORICAL META SYNC")
        print("START:", start_date)
        print("END:", end_date)
        print("TIME RANGE:", params["time_range"])
        print("===================================")

        all_insights = []

        next_url = url

        while next_url:

            response = requests.get(
                next_url,
                params=params if next_url == url else None,
                timeout=30,
            )

            data = response.json()

            if "error" in data:
                return {
                    "success": False,
                    "error": data["error"],
                }

            all_insights.extend(data.get("data", []))

            paging = data.get("paging", {})

            next_url = paging.get("next")

            # The provider's paging URL can contain the access token.

        print("TOTAL ROWS =", len(all_insights))

        inserted = 0
        updated = 0

        for insight in all_insights:

            print("PROCESSING:", insight.get("date_start"))

            stats_date = datetime.strptime(
                insight["date_start"],
                "%Y-%m-%d",
            ).date()

            existing = (
                db.query(MetaDailyStats)
                .filter(MetaDailyStats.stats_date == stats_date)
                .first()
            )

            actions = insight.get("actions", [])
            costs = insight.get("cost_per_action_type", [])

            def get_action_value(action_type):

                for action in actions:

                    if action.get("action_type") == action_type:
                        return float(action.get("value", 0))

                return 0

            def get_cost_value(action_type):

                for item in costs:

                    if item.get("action_type") == action_type:
                        return float(item.get("value", 0))

                return 0

            instagram_messages = get_action_value(
                "onsite_conversion.messaging_conversation_started_7d"
            ) or get_action_value("onsite_conversion.total_messaging_connection")

            link_clicks = get_action_value("link_click")

            landing_page_views = get_action_value("landing_page_view")

            leads = get_action_value("lead")

            cost_per_instagram_message = get_cost_value(
                "onsite_conversion.messaging_conversation_started_7d"
            )

            if existing:

                updated += 1

            else:

                existing = MetaDailyStats(stats_date=stats_date)

                db.add(existing)

                inserted += 1

            existing.spend = float(insight.get("spend", 0))

            existing.impressions = int(insight.get("impressions", 0))

            existing.reach = int(insight.get("reach", 0))

            existing.clicks = int(insight.get("clicks", 0))

            existing.cpc = float(insight.get("cpc", 0))

            existing.cpm = float(insight.get("cpm", 0))

            existing.ctr = float(insight.get("ctr", 0))

            existing.frequency = float(insight.get("frequency", 0))

            existing.instagram_messages = int(instagram_messages)

            existing.link_clicks = int(link_clicks)

            existing.landing_page_views = int(landing_page_views)

            existing.leads = int(leads)

            existing.cost_per_instagram_message = float(cost_per_instagram_message)

        db.commit()

        print("HISTORICAL SYNC COMPLETED")

        return {
            "success": True,
            "inserted": inserted,
            "updated": updated,
            "total_days": inserted + updated,
        }
