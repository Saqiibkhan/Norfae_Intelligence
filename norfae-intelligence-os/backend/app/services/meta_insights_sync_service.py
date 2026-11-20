from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import logging
import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import MetaAdInsight, MetaSyncRun, MetaSyncState, SettingsModel
from app.services.meta_client import MetaAPIError, MetaClient

STALE_RUN_AFTER = timedelta(hours=1)
LEVELS = ("account", "campaign", "adset", "ad")
logger = logging.getLogger(__name__)


class MetaSyncError(Exception):
    def __init__(self, category: str, summary: str, status_code: int = 409):
        super().__init__(summary)
        self.category = category
        self.summary = summary
        self.status_code = status_code


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _decimal(value):
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Invalid Meta metric") from None
    if not number.is_finite() or abs(number) > Decimal("9999999999999999"):
        raise ValueError("Meta metric is outside the supported range")
    return number


def _integer(value):
    number = _decimal(value)
    if number is None:
        return None
    if number < 0 or number != number.to_integral_value() or number > 2_147_483_647:
        raise ValueError("Invalid Meta count")
    return int(number)


def _json_list(value):
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("Invalid Meta action metric")
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def _parse_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Invalid Meta insight date")
    return date.fromisoformat(value)


def _bounded_text(value, maximum: int, *, required: bool = False):
    if value is None and not required:
        return None
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ValueError("Invalid Meta text field")
    text = str(value).strip()
    if (required and not text) or len(text) > maximum:
        raise ValueError("Meta text field is outside the supported range")
    return text


class MetaInsightsSyncService:
    @staticmethod
    def client_for_account_listing(db: Session, business_id: int):
        settings = db.query(SettingsModel).filter(SettingsModel.business_id == business_id).first()
        if not settings or not settings.meta_access_token:
            raise MetaSyncError("configuration_missing", "Meta access token is not configured.", 409)
        try:
            return MetaClient(settings.meta_access_token)
        except ValueError:
            raise MetaSyncError("configuration_invalid", "Meta integration settings are invalid.", 409) from None

    @staticmethod
    def client_for_business(db: Session, business_id: int):
        settings = db.query(SettingsModel).filter(SettingsModel.business_id == business_id).first()
        if not settings or not settings.meta_account_id or not settings.meta_access_token:
            raise MetaSyncError("configuration_missing", "Meta account and access token are not configured.", 409)
        try:
            account_id = MetaClient.normalize_account_id(settings.meta_account_id)
            client = MetaClient(settings.meta_access_token)
        except ValueError:
            raise MetaSyncError("configuration_invalid", "Meta integration settings are invalid.", 409) from None
        return client, account_id

    @staticmethod
    def status(db: Session, business_id: int):
        settings = db.query(SettingsModel).filter(SettingsModel.business_id == business_id).first()
        state = db.query(MetaSyncState).filter(MetaSyncState.business_id == business_id).first()
        configured = bool(settings and settings.meta_account_id and settings.meta_access_token)
        selected = settings.meta_account_id if settings else None
        if isinstance(selected, str) and selected.startswith("act_"):
            selected = selected[4:]
        return {
            "configured": configured,
            "selected_account_id": selected,
            "connected": bool(configured and state and state.selected_account_id == selected and state.last_synced_at),
            "last_synced_at": state.last_synced_at if state else None,
            "message": "Meta access was verified by a successful prior sync." if configured and state and state.last_synced_at else "Meta credentials are configured; provider access has not been verified by a successful sync." if configured else "Meta account and access token are not configured.",
        }

    @staticmethod
    def _begin(db: Session, business_id: int, user_id: int | None,
               start_date: date, end_date: date):
        now = _now()
        state = db.query(MetaSyncState).filter(
            MetaSyncState.business_id == business_id
        ).with_for_update().first()
        if state is None:
            state = MetaSyncState(business_id=business_id)
            db.add(state)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                state = db.query(MetaSyncState).filter(
                    MetaSyncState.business_id == business_id
                ).with_for_update().first()
        if state is None:
            db.rollback()
            raise MetaSyncError("database_error", "Meta sync state could not be initialized.", 500)
        settings = db.query(SettingsModel).filter(SettingsModel.business_id == business_id).first()
        if not settings or not settings.meta_account_id or not settings.meta_access_token:
            db.rollback()
            raise MetaSyncError("configuration_missing", "Meta account and access token are not configured.", 409)
        try:
            account_id = MetaClient.normalize_account_id(settings.meta_account_id)
            client = MetaClient(settings.meta_access_token)
        except ValueError:
            db.rollback()
            raise MetaSyncError("configuration_invalid", "Meta integration settings are invalid.", 409) from None
        if state.running_since and state.running_since > now - STALE_RUN_AFTER:
            db.rollback()
            raise MetaSyncError("sync_in_progress", "A Meta insights sync is already running.", 409)
        if state.running_since:
            stale = db.query(MetaSyncRun).filter(
                MetaSyncRun.business_id == business_id,
                MetaSyncRun.status == "running",
            ).all()
            for old_run in stale:
                old_run.status = "failed"
                old_run.completed_at = now
                old_run.error_category = "lease_expired"
                old_run.error_summary = "Previous Meta sync stopped before completion."
        if state.selected_account_id and state.selected_account_id != account_id:
            successful = db.query(MetaSyncRun.id).filter(
                MetaSyncRun.business_id == business_id,
                MetaSyncRun.status.in_(("completed", "partially_completed")),
            ).first()
            if successful:
                db.rollback()
                raise MetaSyncError("account_changed", "This business has synchronized a different Meta account; a reviewed data reset is required before switching accounts.", 409)
        state.selected_account_id = account_id
        state.running_since = now
        run = MetaSyncRun(
            business_id=business_id, user_id=user_id, account_id=account_id,
            start_date=start_date, end_date=end_date, status="running", started_at=now,
        )
        db.add(run)
        db.flush()
        state.active_run_id = run.id
        db.commit()
        db.refresh(run)
        return client, account_id, run

    @staticmethod
    def _run_response(run):
        return {
            "run_id": run.id, "account_id": run.account_id,
            "start_date": run.start_date, "end_date": run.end_date,
            "status": run.status, "records_fetched": run.records_fetched,
            "records_created": run.records_created, "records_updated": run.records_updated,
            "records_skipped": run.records_skipped, "error_category": run.error_category,
            "message": run.error_summary, "started_at": run.started_at,
            "completed_at": run.completed_at,
        }

    @staticmethod
    def _finish(db: Session, business_id: int, run_id: int, *, status: str,
                counts: dict, error: MetaAPIError | MetaSyncError | None = None):
        state = db.query(MetaSyncState).filter(
            MetaSyncState.business_id == business_id
        ).with_for_update().first()
        run = db.query(MetaSyncRun).filter(
            MetaSyncRun.id == run_id, MetaSyncRun.business_id == business_id
        ).with_for_update().first()
        if not state or not run:
            raise MetaSyncError("database_error", "Meta sync state could not be finalized.", 500)
        owns_lease = state.active_run_id == run_id
        if not owns_lease:
            if run.status == "running":
                run.status = "failed"
                run.error_category = "lease_expired"
                run.error_summary = "Meta sync lost its active lease before completion."
                run.completed_at = _now()
            db.commit()
            return MetaInsightsSyncService._run_response(run)
        state.running_since = None
        state.active_run_id = None
        if status == "completed":
            state.last_synced_at = _now()
        run.status = status
        run.completed_at = _now()
        for key in ("fetched", "created", "updated", "skipped"):
            setattr(run, f"records_{key}", counts.get(key, 0))
        if error:
            run.error_category = error.category
            summary = getattr(error, "summary", None) or getattr(error, "safe_summary", "Meta sync failed.")
            run.error_summary = summary[:300]
        db.commit()
        return MetaInsightsSyncService._run_response(run)

    @staticmethod
    def _prepare_row(raw: dict, level: str, account_id: str, currency: str | None,
                     start_date: date, end_date: date):
        provider_account = raw.get("account_id")
        if provider_account is not None and MetaClient.normalize_account_id(str(provider_account)) != account_id:
            raise ValueError("Meta insight account mismatch")
        date_start = _parse_date(raw.get("date_start"))
        date_stop = _parse_date(raw.get("date_stop"))
        if date_start > date_stop or date_start < start_date or date_stop > end_date:
            raise ValueError("Meta insight date is outside the requested range")
        id_key = {"account": "account_id", "campaign": "campaign_id", "adset": "adset_id", "ad": "ad_id"}[level]
        entity_id = raw.get(id_key)
        if level == "account" and entity_id and str(entity_id).startswith("act_"):
            entity_id = str(entity_id)[4:]
        entity_id = _bounded_text(entity_id, 64, required=True)
        supplied_currency = raw.get("account_currency") or currency
        if supplied_currency is not None and not re.fullmatch(r"[A-Za-z]{3}", str(supplied_currency)):
            raise ValueError("Invalid Meta account currency")
        names = {
            "entity_name": _bounded_text(raw.get({"account": "account_name", "campaign": "campaign_name", "adset": "adset_name", "ad": "ad_name"}[level]), 255),
            "campaign_name": _bounded_text(raw.get("campaign_name"), 255),
            "adset_name": _bounded_text(raw.get("adset_name"), 255),
            "ad_name": _bounded_text(raw.get("ad_name"), 255),
        }
        ids = {}
        for key in ("campaign_id", "adset_id", "ad_id"):
            ids[key] = _bounded_text(raw.get(key), 64)
        return {
            "account_id": account_id, "currency": str(supplied_currency).upper() if supplied_currency else None,
            "level": level, "entity_id": entity_id,
            **names,
            **ids,
            "date_start": date_start, "date_stop": date_stop,
            "spend": _decimal(raw.get("spend")),
            "impressions": _integer(raw.get("impressions")), "reach": _integer(raw.get("reach")),
            "clicks": _integer(raw.get("clicks")), "inline_link_clicks": _integer(raw.get("inline_link_clicks")),
            "ctr": _decimal(raw.get("ctr")), "cpc": _decimal(raw.get("cpc")),
            "cpm": _decimal(raw.get("cpm")), "frequency": _decimal(raw.get("frequency")),
            "actions_json": _json_list(raw.get("actions")),
            "action_values_json": _json_list(raw.get("action_values")),
            "cost_per_action_type_json": _json_list(raw.get("cost_per_action_type")),
            "action_attribution_windows_json": '["default"]',
            "action_report_time": "mixed",
            "updated_at": _now(),
        }

    @staticmethod
    def sync(db: Session, business_id: int, user_id: int, start_date: date, end_date: date):
        if start_date > end_date or (end_date - start_date).days > 91:
            raise MetaSyncError("invalid_date_range", "Meta sync range must be ordered and no longer than 92 days.", 422)
        client, account_id, run = MetaInsightsSyncService._begin(db, business_id, user_id, start_date, end_date)
        counts = {"fetched": 0, "created": 0, "updated": 0, "skipped": 0}
        try:
            account = client.get_account(account_id)
            currency = account.get("currency")
            prepared = []
            errors = []
            for level in LEVELS:
                try:
                    raw_rows = client.get_insights(account_id, level, start_date.isoformat(), end_date.isoformat())
                except MetaAPIError as error:
                    errors.append(error)
                    continue
                counts["fetched"] += len(raw_rows)
                for raw in raw_rows:
                    try:
                        prepared.append(MetaInsightsSyncService._prepare_row(raw, level, account_id, currency, start_date, end_date))
                    except (ValueError, TypeError, InvalidOperation):
                        counts["skipped"] += 1
            state = db.query(MetaSyncState).filter(
                MetaSyncState.business_id == business_id
            ).with_for_update().first()
            if not state or state.active_run_id != run.id:
                raise MetaSyncError("lease_expired", "Meta sync lost its active lease before persistence.", 409)
            existing = db.query(MetaAdInsight).filter(
                MetaAdInsight.account_id == account_id,
                MetaAdInsight.date_start >= start_date,
                MetaAdInsight.date_stop <= end_date,
            ).all()
            index = {(row.level, row.entity_id, row.date_start, row.date_stop): row for row in existing}
            seen = set()
            for values in prepared:
                key = (values["level"], values["entity_id"], values["date_start"], values["date_stop"])
                if key in seen:
                    counts["skipped"] += 1
                    continue
                seen.add(key)
                row = index.get(key)
                if row is None:
                    row = MetaAdInsight(business_id=business_id, **values)
                    db.add(row)
                    index[key] = row
                    counts["created"] += 1
                else:
                    for field, value in values.items():
                        setattr(row, field, value)
                    counts["updated"] += 1
            db.flush()
            status = "failed" if errors and not prepared else "partially_completed" if errors or counts["skipped"] else "completed"
            error = errors[0] if errors else MetaSyncError("invalid_records", "Some Meta insight rows were skipped.") if counts["skipped"] else None
            result = MetaInsightsSyncService._finish(db, business_id, run.id, status=status, counts=counts, error=error)
            return {"status": status, "run": result}
        except (MetaAPIError, MetaSyncError) as error:
            db.rollback()
            result = MetaInsightsSyncService._finish(db, business_id, run.id, status="failed", counts=counts, error=error)
            return {"status": "failed", "run": result}
        except Exception as unexpected:
            logger.warning(
                "Meta insights sync failed during persistence",
                extra={"business_id": business_id, "error_type": type(unexpected).__name__},
            )
            db.rollback()
            error = MetaSyncError("database_error", "Meta insights sync failed; no insight changes from this run were retained.", 500)
            try:
                result = MetaInsightsSyncService._finish(db, business_id, run.id, status="failed", counts=counts, error=error)
                return {"status": "failed", "run": result}
            except Exception:
                raise error from None

    @staticmethod
    def history(db: Session, business_id: int, limit: int = 50):
        return [MetaInsightsSyncService._run_response(row) for row in db.query(MetaSyncRun).filter(
            MetaSyncRun.business_id == business_id
        ).order_by(MetaSyncRun.started_at.desc(), MetaSyncRun.id.desc()).limit(limit).all()]

    @staticmethod
    def insight_rows(db: Session, business_id: int, account_id: str, level: str,
                     start_date: date | None = None, end_date: date | None = None):
        query = db.query(MetaAdInsight).filter(
            MetaAdInsight.business_id == business_id,
            MetaAdInsight.account_id == account_id,
            MetaAdInsight.level == level,
        )
        if start_date:
            query = query.filter(MetaAdInsight.date_start >= start_date)
        if end_date:
            query = query.filter(MetaAdInsight.date_stop <= end_date)
        return query.order_by(MetaAdInsight.date_start, MetaAdInsight.entity_id).all()
