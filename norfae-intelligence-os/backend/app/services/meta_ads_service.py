import json
from datetime import date
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.models import MetaAdInsight, SettingsModel
from app.core.timezone import pakistan_now
from app.services.meta_client import MetaClient


def _number(value):
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _sum(values):
    parsed = [_number(value) for value in values]
    if not parsed or any(value is None for value in parsed):
        return None
    return sum(parsed, Decimal("0"))


class MetaAdsService:
    """Read-only reporting over imported Meta insight rows; never makes provider calls."""

    @staticmethod
    def get_primary_result(actions):
        actions = actions if isinstance(actions, list) else []
        values = {}
        for item in actions:
            if not isinstance(item, dict) or not item.get("action_type"):
                continue
            parsed = _number(item.get("value"))
            if parsed is not None:
                values[item["action_type"]] = parsed

        def first(*action_types):
            for action_type in action_types:
                if action_type in values:
                    value = values[action_type]
                    return int(value) if value == value.to_integral_value() else float(value)
            return 0

        purchase_types = (
            "purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase",
            "offsite_conversion.purchase", "website_purchase",
        )
        reported = sorted(action_type for action_type in values if action_type in purchase_types)
        messages = first("onsite_conversion.messaging_conversation_started_7d") or first(
            "onsite_conversion.total_messaging_connection"
        )
        return {
            "messages": messages,
            "purchases": first(*purchase_types),
            "purchase_data_available": bool(reported),
            "reported_purchase_action_types": reported,
            "leads": first("lead"),
        }

    @staticmethod
    def _account_rows(db: Session, start_date=None, end_date=None):
        settings = db.query(SettingsModel).first()
        if not settings or not settings.meta_account_id:
            return None, "Meta account is not configured."
        try:
            account_id = MetaClient.normalize_account_id(settings.meta_account_id)
        except ValueError:
            return None, "Meta account configuration is invalid."
        query = db.query(MetaAdInsight).filter(
            MetaAdInsight.account_id == account_id,
            MetaAdInsight.level == "account",
        )
        if start_date:
            start = date.fromisoformat(start_date) if isinstance(start_date, str) else start_date
            query = query.filter(MetaAdInsight.date_start >= start)
        if end_date:
            end = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
            query = query.filter(MetaAdInsight.date_stop <= end)
        return query.order_by(MetaAdInsight.date_start).all(), None

    @staticmethod
    def _actions(row, field="actions_json"):
        value = getattr(row, field, None)
        try:
            decoded = json.loads(value) if value else []
        except (ValueError, TypeError):
            return []
        return decoded if isinstance(decoded, list) else []

    @classmethod
    def _entity_rows(cls, db: Session, level: str, start_date=None, end_date=None):
        settings = db.query(SettingsModel).first()
        if not settings or not settings.meta_account_id:
            return None, "Meta account is not configured."
        try:
            account_id = MetaClient.normalize_account_id(settings.meta_account_id)
        except ValueError:
            return None, "Meta account configuration is invalid."
        query = db.query(MetaAdInsight).filter(
            MetaAdInsight.account_id == account_id,
            MetaAdInsight.level == level,
        )
        if start_date:
            query = query.filter(MetaAdInsight.date_start >= date.fromisoformat(start_date) if isinstance(start_date, str) else MetaAdInsight.date_start >= start_date)
        if end_date:
            query = query.filter(MetaAdInsight.date_stop <= date.fromisoformat(end_date) if isinstance(end_date, str) else MetaAdInsight.date_stop <= end_date)
        return query.order_by(MetaAdInsight.date_start, MetaAdInsight.entity_id).all(), None

    @staticmethod
    def _format_entity(row, level):
        actions = MetaAdsService._actions(row)
        results = MetaAdsService.get_primary_result(actions)
        entity_id_field = {"campaign": "campaign_id", "adset": "adset_id", "ad": "ad_id"}[level]
        entity_name_field = {"campaign": "campaign_name", "adset": "adset_name", "ad": "ad_name"}[level]
        return {
            entity_id_field: row.entity_id,
            entity_name_field: row.entity_name,
            "campaign_id": row.campaign_id,
            "campaign_name": row.campaign_name,
            "adset_id": row.adset_id,
            "adset_name": row.adset_name,
            "ad_id": row.ad_id,
            "ad_name": row.ad_name,
            "spend": float(row.spend) if row.spend is not None else None,
            "impressions": row.impressions,
            "reach": row.reach,
            "clicks": row.clicks,
            "ctr": float(row.ctr) if row.ctr is not None else None,
            "cpc": float(row.cpc) if row.cpc is not None else None,
            "cpm": float(row.cpm) if row.cpm is not None else None,
            "frequency": float(row.frequency) if row.frequency is not None else None,
            "link_clicks": row.inline_link_clicks,
            "sales": results["purchases"],
            "purchase_data_available": results["purchase_data_available"],
            "reported_purchase_action_types": results["reported_purchase_action_types"],
            "leads": results["leads"],
            "instagram_messages": results["messages"],
            "date_start": row.date_start.isoformat(),
            "date_stop": row.date_stop.isoformat(),
            "currency": row.currency,
            "action_attribution_windows": json.loads(row.action_attribution_windows_json),
            "action_report_time": row.action_report_time,
        }

    @staticmethod
    def _sum_action_rows(rows, field):
        arrays = []
        for row in rows:
            value = getattr(row, field)
            if not value:
                return None
            try:
                decoded = json.loads(value)
            except (ValueError, TypeError):
                return None
            if not isinstance(decoded, list):
                return None
            arrays.append(decoded)
        combined = {}
        for array in arrays:
            for item in array:
                if not isinstance(item, dict) or not item.get("action_type"):
                    continue
                key = item["action_type"]
                parsed = _number(item.get("value"))
                if parsed is None:
                    continue
                combined[key] = combined.get(key, Decimal("0")) + parsed
        return json.dumps([
            {"action_type": key, "value": format(value, "f")}
            for key, value in sorted(combined.items())
        ], separators=(",", ":"))

    @classmethod
    def _aggregate_entities(cls, rows, level):
        grouped = {}
        for row in rows:
            grouped.setdefault(row.entity_id, []).append(row)
        result = []
        for entity_rows in grouped.values():
            first = entity_rows[0]
            unique_days = {row.date_start for row in entity_rows}
            spend = _sum([row.spend for row in entity_rows])
            impressions = _sum([row.impressions for row in entity_rows])
            clicks = _sum([row.clicks for row in entity_rows])
            link_clicks = _sum([row.inline_link_clicks for row in entity_rows])
            reach = first.reach if len(unique_days) == 1 and len(entity_rows) == 1 else None
            ctr = clicks / impressions * 100 if clicks is not None and impressions else None
            cpc = spend / clicks if spend is not None and clicks else None
            cpm = spend / impressions * 1000 if spend is not None and impressions else None
            frequency = impressions / reach if impressions is not None and reach else None
            result.append(SimpleNamespace(
                entity_id=first.entity_id, entity_name=first.entity_name,
                campaign_id=first.campaign_id, campaign_name=first.campaign_name,
                adset_id=first.adset_id, adset_name=first.adset_name,
                ad_id=first.ad_id, ad_name=first.ad_name,
                spend=spend, impressions=impressions, reach=reach, clicks=clicks,
                inline_link_clicks=link_clicks, ctr=ctr, cpc=cpc, cpm=cpm,
                frequency=frequency, date_start=min(unique_days), date_stop=max(unique_days),
                currency=first.currency,
                actions_json=cls._sum_action_rows(entity_rows, "actions_json"),
                action_values_json=cls._sum_action_rows(entity_rows, "action_values_json"),
                action_attribution_windows_json=first.action_attribution_windows_json,
                action_report_time=first.action_report_time,
            ))
        return result

    @classmethod
    def get_account_overview(cls, db: Session, start_date=None, end_date=None):
        rows, error = cls._account_rows(db, start_date, end_date)
        if error:
            return {"success": False, "message": error}
        if not rows:
            return {"success": True, "overview": {}, "source": "stored Meta account insights"}
        spend = _sum([row.spend for row in rows])
        impressions = _sum([row.impressions for row in rows])
        clicks = _sum([row.clicks for row in rows])
        reach = rows[0].reach if len(rows) == 1 else None
        actions = [item for row in rows for item in cls._actions(row)]
        result = cls.get_primary_result(actions)
        ctr = clicks / impressions * 100 if clicks is not None and impressions else None
        cpc = spend / clicks if spend is not None and clicks else None
        cpm = spend / impressions * 1000 if spend is not None and impressions else None
        return {
            "success": True, "source": "stored Meta account insights",
            "attribution_note": "Purchase, lead, and message actions are Meta-reported and follow the stored attribution request; they are not independently verified Norfae orders.",
            "overview": {
                "spend": float(spend) if spend is not None else None,
                "impressions": int(impressions) if impressions is not None else None,
                "reach": int(reach) if reach is not None else None,
                "clicks": int(clicks) if clicks is not None else None,
                "ctr": float(ctr) if ctr is not None else None,
                "cpc": float(cpc) if cpc is not None else None,
                "cpm": float(cpm) if cpm is not None else None,
                "instagram_messages": result["messages"],
                "sales": result["purchases"],
                "purchase_data_available": result["purchase_data_available"],
                "reported_purchase_action_types": result["reported_purchase_action_types"],
                "leads": result["leads"],
                "link_clicks": sum((row.inline_link_clicks or 0) for row in rows),
                "frequency": float(impressions / reach) if impressions is not None and reach else None,
                "currency": rows[0].currency,
                "reach_note": None if len(rows) == 1 else "Daily reach overlaps across dates and cannot be added to a unique-period reach total.",
            },
        }

    @staticmethod
    def get_today_stats(db: Session):
        today = pakistan_now().date()
        rows, error = MetaAdsService._account_rows(db, today, today)
        if error:
            return {"success": False, "message": error}
        if not rows:
            return {"success": False, "message": "No imported Meta account insights for today."}
        overview = MetaAdsService.get_account_overview(db, today, today).get("overview", {})
        return {"success": True, "data": {"date": today.isoformat(), **overview}}

    @classmethod
    def get_analysis(cls, db: Session):
        rows, error = cls._account_rows(db)
        if error:
            return {"success": False, "message": error}
        if not rows:
            return {"success": False, "message": "No imported Meta account insights are available."}
        overview = cls.get_account_overview(db)["overview"]
        return {
            "success": True, "analysis": {
                "total_spend": overview["spend"],
                "total_messages": overview["instagram_messages"],
                "average_ctr": overview["ctr"],
                "average_cpc": overview["cpc"],
                "average_message_cost": None,
                "purchase_data_available": overview["purchase_data_available"],
                "recommendation": "Review Meta-reported metrics alongside deterministic Norfae outcomes; no automated scaling recommendation is generated from incomplete attribution data.",
            },
        }

    @classmethod
    def get_campaigns(cls, db: Session, start_date=None, end_date=None):
        return cls._get_entities(db, "campaign", start_date, end_date, "campaigns")

    @classmethod
    def get_adsets(cls, db: Session, start_date=None, end_date=None):
        return cls._get_entities(db, "adset", start_date, end_date, "adsets")

    @classmethod
    def get_ads(cls, db: Session, start_date=None, end_date=None):
        return cls._get_entities(db, "ad", start_date, end_date, "ads")

    @classmethod
    def _get_entities(cls, db: Session, level, start_date, end_date, key):
        rows, error = cls._entity_rows(db, level, start_date, end_date)
        if error:
            return {"success": False, "message": error}
        return {
            "success": True, key: [cls._format_entity(row, level) for row in cls._aggregate_entities(rows, level)],
            "source": "stored Meta-reported insights",
            "attribution_note": "Action counts and values are Meta-reported under the stored attribution request, not independently verified Norfae outcomes.",
        }
