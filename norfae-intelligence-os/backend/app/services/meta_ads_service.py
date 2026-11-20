import json
import requests

from sqlalchemy.orm import Session

from app.models.settings_model import SettingsModel

from app.models.meta_daily_stats_model import MetaDailyStats


class MetaAdsService:

    @staticmethod
    def get_primary_result(actions):

        def get_action(action_type):
            for action in actions:
                if action.get("action_type") == action_type:
                    return int(float(action.get("value", 0)))
            return 0

        messages = get_action(
            "onsite_conversion.messaging_conversation_started_7d"
        ) or get_action("onsite_conversion.total_messaging_connection")

        purchases = (
            get_action("purchase")
            or get_action("omni_purchase")
            or get_action("offsite_conversion.fb_pixel_purchase")
            or get_action("offsite_conversion.purchase")
            or get_action("website_purchase")
        )

        leads = get_action("lead")
        purchase_action_types = {
            "purchase",
            "omni_purchase",
            "offsite_conversion.fb_pixel_purchase",
            "offsite_conversion.purchase",
            "website_purchase",
        }
        reported_purchase_types = sorted(
            {
                item.get("action_type")
                for item in actions
                if item.get("action_type") in purchase_action_types
            }
        )

        return {
            "messages": messages,
            "purchases": purchases,
            "purchase_data_available": bool(reported_purchase_types),
            "reported_purchase_action_types": reported_purchase_types,
            "leads": leads,
        }

    @staticmethod
    def get_account_overview(db: Session, start_date=None, end_date=None):

        settings = db.query(SettingsModel).first()

        if not settings:
            return {"success": False, "message": "Settings not found"}

        access_token = settings.meta_access_token
        account_id = settings.meta_account_id

        if not access_token or not account_id:
            return {"success": False, "message": "Meta credentials missing"}

        # =========================================
        # REMOVE act_ IF USER ALREADY ENTERED IT
        # =========================================

        account_id = account_id.replace("act_", "")

        # =========================================
        # META API URL
        # =========================================

        url = f"https://graph.facebook.com/v25.0/act_{account_id}/insights"

        # =========================================
        # IMPORTANT METRICS
        # =========================================

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
        }

        if start_date and end_date:

            params["time_range"] = json.dumps({"since": start_date, "until": end_date})

        else:

            params["date_preset"] = "this_month"

        print("START DATE:", start_date)
        print("END DATE:", end_date)
        print("TIME RANGE:", params.get("time_range"))
        response = requests.get(
            url,
            params=params,
            timeout=30,
        )

        data = response.json()

        if "error" in data:
            return {"success": False, "error": data["error"]}

        insights = data.get("data", [])

        if not insights:
            return {"success": True, "overview": {}}

        insight = insights[0]

        # =========================================
        # ACTION EXTRACTION
        # =========================================

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

        # =========================================
        # INSTAGRAM + WHATSAPP
        # =========================================

        results = MetaAdsService.get_primary_result(actions)

        instagram_messages = results["messages"]
        sales = results["purchases"]
        leads = results["leads"]

        # =========================================
        # WEBSITE TRAFFIC
        # =========================================

        link_clicks = get_action_value("link_click")

        landing_page_views = get_action_value("landing_page_view")

        # =========================================
        # COSTS
        # =========================================

        cost_per_message = get_cost_value(
            "onsite_conversion.messaging_conversation_started_7d"
        )

        if cost_per_message == 0:
            cost_per_message = get_cost_value(
                "onsite_conversion.total_messaging_connection"
            )

        # =========================================
        # FINAL RESPONSE
        # =========================================

        return {
            "success": True,
            "overview": {
                # =========================
                # SPEND
                # =========================
                "spend": round(float(insight.get("spend", 0)), 2),
                # =========================
                # TRAFFIC
                # =========================
                "impressions": int(insight.get("impressions", 0)),
                "reach": int(insight.get("reach", 0)),
                "clicks": int(insight.get("clicks", 0)),
                "ctr": round(float(insight.get("ctr", 0)), 2),
                "cpc": round(float(insight.get("cpc", 0)), 2),
                "cpm": round(float(insight.get("cpm", 0)), 2),
                "frequency": round(float(insight.get("frequency", 0)), 2),
                # =========================
                # MESSAGES
                # =========================
                "instagram_messages": int(instagram_messages),
                "sales": int(sales),
                # =========================
                # WEBSITE
                # =========================
                "link_clicks": int(link_clicks),
                "landing_page_views": int(landing_page_views),
                # =========================
                # LEADS
                # =========================
                "leads": int(leads),
                # =========================
                # COST ANALYSIS
                # =========================
                "cost_per_instagram_message": round(cost_per_message, 2),
            },
        }

    @staticmethod
    def get_today_stats(db: Session):

        from datetime import datetime
        from zoneinfo import ZoneInfo

        today = datetime.now(ZoneInfo("Asia/Karachi")).date()

        latest = (
            db.query(MetaDailyStats).filter(MetaDailyStats.stats_date == today).first()
        )

        if not latest:

            return {"success": False, "message": "No stats found"}

        return {
            "success": True,
            "data": {
                "date": str(latest.stats_date),
                "spend": latest.spend,
                "impressions": latest.impressions,
                "reach": latest.reach,
                "clicks": latest.clicks,
                "ctr": latest.ctr,
                "cpc": latest.cpc,
                "cpm": latest.cpm,
                "frequency": latest.frequency,
                "instagram_messages": latest.instagram_messages,
                "link_clicks": latest.link_clicks,
                "landing_page_views": latest.landing_page_views,
                "leads": latest.leads,
                "cost_per_instagram_message": (latest.cost_per_instagram_message),
            },
        }

    @staticmethod
    def get_analysis(db: Session):

        stats = db.query(MetaDailyStats).all()

        if not stats:

            return {"success": False, "message": "No stats found"}

        total_spend = sum(x.spend for x in stats)

        total_messages = sum(x.instagram_messages for x in stats)

        avg_ctr = sum(x.ctr for x in stats) / len(stats)

        avg_cpc = sum(x.cpc for x in stats) / len(stats)

        avg_message_cost = sum(x.cost_per_instagram_message for x in stats) / len(stats)

        best_ctr_day = max(stats, key=lambda x: x.ctr)

        worst_ctr_day = min(stats, key=lambda x: x.ctr)

        best_cpc_day = min(stats, key=lambda x: x.cpc)

        worst_cpc_day = max(stats, key=lambda x: x.cpc)

        # =====================
        # RECOMMENDATION
        # =====================

        recommendation = "Stable"

        if avg_ctr >= 2 and avg_message_cost <= 60:

            recommendation = "Scaling Opportunity"

        elif avg_ctr < 1.5:

            recommendation = "Weak Performance"

        return {
            "success": True,
            "analysis": {
                "total_spend": round(total_spend, 2),
                "total_messages": total_messages,
                "average_ctr": round(avg_ctr, 2),
                "average_cpc": round(avg_cpc, 2),
                "average_message_cost": round(avg_message_cost, 2),
                "best_ctr_day": str(best_ctr_day.stats_date),
                "worst_ctr_day": str(worst_ctr_day.stats_date),
                "best_cpc_day": str(best_cpc_day.stats_date),
                "worst_cpc_day": str(worst_cpc_day.stats_date),
                "recommendation": recommendation,
            },
        }

    @staticmethod
    def get_campaigns(db: Session, start_date=None, end_date=None):

        settings = db.query(SettingsModel).first()

        if not settings:
            return {"success": False, "message": "Settings not found"}

        access_token = settings.meta_access_token
        account_id = settings.meta_account_id

        if not access_token or not account_id:
            return {"success": False, "message": "Meta credentials missing"}

        account_id = account_id.replace("act_", "")

        url = f"https://graph.facebook.com/" f"v25.0/act_{account_id}/insights"

        params = {
            "access_token": access_token,
            "level": "campaign",
            "fields": ",".join(
                [
                    "campaign_name",
                    "campaign_id",
                    "spend",
                    "impressions",
                    "reach",
                    "clicks",
                    "ctr",
                    "cpc",
                    "cpm",
                    "frequency",
                    "actions",
                ]
            ),
        }

        if start_date and end_date:

            params["time_range"] = json.dumps({"since": start_date, "until": end_date})

        else:

            params["date_preset"] = "this_month"

        print("START DATE:", start_date)
        print("END DATE:", end_date)
        print("TIME RANGE:", params.get("time_range"))

        response = requests.get(
            url,
            params=params,
            timeout=30,
        )

        data = response.json()

        if "error" in data:

            return {"success": False, "error": data["error"]}

        campaigns = []

        for campaign in data.get("data", []):

            actions = campaign.get("actions", [])

            def get_action_value(action_type):

                for action in actions:

                    if action.get("action_type") == action_type:
                        return int(float(action.get("value", 0)))

                return 0

            results = MetaAdsService.get_primary_result(actions)

            instagram_messages = results["messages"]
            sales = results["purchases"]
            leads = results["leads"]

            ctr = float(campaign.get("ctr", 0))

            status = "Stable"

            if ctr >= 2:
                status = "Scaling"

            elif ctr < 1.5:
                status = "Weak"

            campaigns.append(
                {
                    "campaign_id": campaign.get("campaign_id"),
                    "campaign_name": campaign.get("campaign_name"),
                    "spend": round(float(campaign.get("spend", 0)), 2),
                    "impressions": int(campaign.get("impressions", 0)),
                    "reach": int(campaign.get("reach", 0)),
                    "clicks": int(campaign.get("clicks", 0)),
                    "ctr": round(ctr, 2),
                    "cpc": round(float(campaign.get("cpc", 0)), 2),
                    "cpm": round(float(campaign.get("cpm", 0)), 2),
                    "frequency": round(float(campaign.get("frequency", 0)), 2),
                    "instagram_messages": instagram_messages,
                    "sales": sales,
                    "purchase_data_available": results["purchase_data_available"],
                    "reported_purchase_action_types": results["reported_purchase_action_types"],
                    "link_clicks": int(get_action_value("link_click")),
                    "leads": leads,
                    "status": status,
                }
            )

        campaigns.sort(key=lambda x: x["spend"], reverse=True)

        return {"success": True, "campaigns": campaigns}

    @staticmethod
    def get_adsets(db: Session, start_date=None, end_date=None):

        settings = db.query(SettingsModel).first()

        if not settings:
            return {"success": False, "message": "Settings not found"}

        access_token = settings.meta_access_token
        account_id = settings.meta_account_id

        if not access_token or not account_id:
            return {"success": False, "message": "Meta credentials missing"}

        account_id = account_id.replace("act_", "")

        url = f"https://graph.facebook.com/v25.0/act_{account_id}/insights"

        params = {
            "access_token": access_token,
            "level": "adset",
            "fields": ",".join(
                [
                    "campaign_id",
                    "campaign_name",
                    "adset_id",
                    "adset_name",
                    "spend",
                    "impressions",
                    "reach",
                    "clicks",
                    "ctr",
                    "cpc",
                    "cpm",
                    "frequency",
                    "actions",
                ]
            ),
        }

        if start_date and end_date:

            params["time_range"] = json.dumps({"since": start_date, "until": end_date})

        else:

            params["date_preset"] = "this_month"

            print("START DATE:", start_date)
        print("END DATE:", end_date)
        print("TIME RANGE:", params.get("time_range"))

        response = requests.get(
            url,
            params=params,
            timeout=30,
        )

        data = response.json()

        if "error" in data:
            return {"success": False, "error": data["error"]}

        adsets = []

        for adset in data.get("data", []):

            actions = adset.get("actions", [])

            def get_action_value(action_type):

                for action in actions:
                    if action.get("action_type") == action_type:
                        return int(float(action.get("value", 0)))

                return 0

            results = MetaAdsService.get_primary_result(actions)

            instagram_messages = results["messages"]
            sales = results["purchases"]
            leads = results["leads"]

            ctr = float(adset.get("ctr", 0))

            status = "Stable"

            if ctr >= 2:
                status = "Scaling"
            elif ctr < 1.5:
                status = "Weak"

            adsets.append(
                {
                    "campaign_id": adset.get("campaign_id"),
                    "campaign_name": adset.get("campaign_name"),
                    "adset_id": adset.get("adset_id"),
                    "adset_name": adset.get("adset_name"),
                    "spend": round(float(adset.get("spend", 0)), 2),
                    "impressions": int(adset.get("impressions", 0)),
                    "reach": int(adset.get("reach", 0)),
                    "clicks": int(adset.get("clicks", 0)),
                    "ctr": round(ctr, 2),
                    "cpc": round(float(adset.get("cpc", 0)), 2),
                    "cpm": round(float(adset.get("cpm", 0)), 2),
                    "frequency": round(float(adset.get("frequency", 0)), 2),
                    "instagram_messages": instagram_messages,
                    "sales": sales,
                    "purchase_data_available": results["purchase_data_available"],
                    "reported_purchase_action_types": results["reported_purchase_action_types"],
                    "link_clicks": int(get_action_value("link_click")),
                    "leads": leads,
                    "status": status,
                }
            )

        adsets.sort(key=lambda x: x["spend"], reverse=True)

        return {"success": True, "adsets": adsets}

    @staticmethod
    def get_ads(db: Session, start_date=None, end_date=None):

        settings = db.query(SettingsModel).first()

        if not settings:
            return {"success": False, "message": "Settings not found"}

        access_token = settings.meta_access_token
        account_id = settings.meta_account_id

        if not access_token or not account_id:
            return {"success": False, "message": "Meta credentials missing"}

        account_id = account_id.replace("act_", "")

        url = f"https://graph.facebook.com/v25.0/act_{account_id}/insights"

        params = {
            "access_token": access_token,
            "level": "ad",
            "fields": ",".join(
                [
                    "campaign_id",
                    "campaign_name",
                    "adset_id",
                    "adset_name",
                    "ad_id",
                    "ad_name",
                    "spend",
                    "impressions",
                    "reach",
                    "clicks",
                    "ctr",
                    "cpc",
                    "cpm",
                    "frequency",
                    "actions",
                ]
            ),
        }

        if start_date and end_date:

            params["time_range"] = json.dumps({"since": start_date, "until": end_date})

        else:

            params["date_preset"] = "this_month"

            print("START DATE:", start_date)
        print("END DATE:", end_date)
        print("TIME RANGE:", params.get("time_range"))

        response = requests.get(
            url,
            params=params,
            timeout=30,
        )

        data = response.json()

        if "error" in data:
            return {"success": False, "error": data["error"]}

        ads = []

        for ad in data.get("data", []):

            actions = ad.get("actions", [])

            def get_action_value(action_type):

                for action in actions:

                    if action.get("action_type") == action_type:
                        return int(float(action.get("value", 0)))

                return 0

            results = MetaAdsService.get_primary_result(actions)

            instagram_messages = results["messages"]
            sales = results["purchases"]
            leads = results["leads"]

            ctr = float(ad.get("ctr", 0))

            status = "Stable"

            if ctr >= 2:
                status = "Scaling"

            elif ctr < 1.5:
                status = "Weak"

            ads.append(
                {
                    "campaign_id": ad.get("campaign_id"),
                    "campaign_name": ad.get("campaign_name"),
                    "adset_id": ad.get("adset_id"),
                    "adset_name": ad.get("adset_name"),
                    "ad_id": ad.get("ad_id"),
                    "ad_name": ad.get("ad_name"),
                    "spend": round(float(ad.get("spend", 0)), 2),
                    "impressions": int(ad.get("impressions", 0)),
                    "reach": int(ad.get("reach", 0)),
                    "clicks": int(ad.get("clicks", 0)),
                    "ctr": round(ctr, 2),
                    "cpc": round(float(ad.get("cpc", 0)), 2),
                    "cpm": round(float(ad.get("cpm", 0)), 2),
                    "frequency": round(float(ad.get("frequency", 0)), 2),
                    "instagram_messages": instagram_messages,
                    "sales": sales,
                    "purchase_data_available": results["purchase_data_available"],
                    "reported_purchase_action_types": results["reported_purchase_action_types"],
                    "link_clicks": int(get_action_value("link_click")),
                    "leads": leads,
                    "status": status,
                }
            )

        ads.sort(key=lambda x: x["spend"], reverse=True)

        return {"success": True, "ads": ads}
