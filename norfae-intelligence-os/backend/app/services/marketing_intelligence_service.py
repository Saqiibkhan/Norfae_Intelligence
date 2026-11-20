from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models import Expense, MetaDailyStats, SettingsModel
from app.schemas.intelligence_schema import (
    MarketingCampaignDetail,
    MarketingCampaignPage,
    MarketingEntityPerformance,
    MarketingMetric,
    MarketingOverview,
    MarketingTrendPoint,
    MarketingTrendResponse,
)
from app.services.deterministic_profitability_service import DeterministicProfitabilityService
from app.services.meta_ads_service import MetaAdsService

MIN_CONCLUSION_SPEND = Decimal("10.00")
MIN_CONCLUSION_IMPRESSIONS = 100
MIN_CPC_CLICKS = 20
UNUSUAL_CHANGE_PERCENT = Decimal("50")
PURCHASE_VALUE_UNAVAILABLE = "The existing integration does not persist purchase conversion value or attribution windows."


def _decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _metric(value, source=None, note=None) -> MarketingMetric:
    if value is None:
        return MarketingMetric(amount=None, available=False, source=source, note=note)
    amount = _decimal(value)
    if amount is None:
        return MarketingMetric(amount=None, available=False, source=source, note=note)
    return MarketingMetric(
        amount=float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        available=True,
        source=source,
        note=note,
    )


def _sum(values: list[Decimal | None]) -> Decimal | None:
    if not values or any(value is None for value in values):
        return None
    return sum(values, Decimal("0"))


def _rate(numerator, denominator, multiplier=Decimal("1")) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return float((numerator / denominator * multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _date_filters(query, column, start_date: date | None, end_date: date | None):
    if start_date:
        query = query.filter(column >= start_date)
    if end_date:
        query = query.filter(column <= end_date)
    return query


class MarketingIntelligenceService:
    """Read-only account and campaign analysis over stored or Meta-reported data."""

    @staticmethod
    def _validate_period(start_date, end_date):
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must be on or before end_date.")

    @classmethod
    def overview(cls, db: Session, business_id: int, start_date=None, end_date=None) -> MarketingOverview:
        cls._validate_period(start_date, end_date)
        stats_query = db.query(MetaDailyStats).filter(MetaDailyStats.business_id == business_id)
        stats_query = _date_filters(stats_query, MetaDailyStats.stats_date, start_date, end_date)
        stats = stats_query.order_by(MetaDailyStats.stats_date).all()
        stats_by_date = {row.stats_date: row for row in stats if row.stats_date is not None}

        expense_query = db.query(Expense).filter(
            Expense.business_id == business_id,
            Expense.category.in_(("marketing", "advertising")),
        )
        if start_date:
            expense_query = expense_query.filter(
                Expense.expense_date >= datetime.combine(start_date, time.min)
            )
        if end_date:
            expense_query = expense_query.filter(
                Expense.expense_date < datetime.combine(end_date + timedelta(days=1), time.min)
            )
        expenses = expense_query.order_by(Expense.id).all()
        meta_expenses = [e for e in expenses if (e.source or "").strip().casefold() == "meta"]
        other_marketing = [e for e in expenses if (e.source or "").strip().casefold() != "meta"]
        ledger_by_date = defaultdict(list)
        undated_meta_expenses = []
        for expense in meta_expenses:
            expense_day = expense.expense_date.date() if expense.expense_date else None
            if expense_day is None:
                undated_meta_expenses.append(_decimal(expense.amount))
            else:
                ledger_by_date[expense_day].append(_decimal(expense.amount))

        meta_ledger_total = _sum([_decimal(e.amount) for e in meta_expenses])
        other_marketing_total = _sum([_decimal(e.amount) for e in other_marketing])
        overlap_days = 0
        overlap_values = []
        selected_daily_spend: dict[date, Decimal | None] = {}
        for stats_day, row in stats_by_date.items():
            ledger_values = ledger_by_date.get(stats_day, [])
            if ledger_values:
                overlap_days += 1
                overlap_values.extend(ledger_values)
            primary = _decimal(row.spend)
            if primary is None and ledger_values:
                primary = _sum(ledger_values)
            selected_daily_spend[stats_day] = primary
        for ledger_day, ledger_values in ledger_by_date.items():
            if ledger_day not in stats_by_date:
                selected_daily_spend[ledger_day] = _sum(ledger_values)

        warnings = []
        if not stats and not meta_expenses:
            warnings.append("No stored Meta daily statistics or Meta spend ledger records are available for this period.")
        if overlap_days:
            warnings.append("Meta daily spend and Meta-sourced marketing expenses overlap; daily statistics were preferred and duplicate ledger spend was excluded.")
        if undated_meta_expenses:
            if stats:
                warnings.append("Undated Meta expense rows were excluded from effective spend because they cannot safely be matched to daily statistics.")
            elif not start_date and not end_date:
                warnings.append("Meta expenses without dates are included only because no daily statistics exist; they cannot be placed in trends.")
                for index, amount in enumerate(undated_meta_expenses):
                    selected_daily_spend[date.min + timedelta(days=index)] = amount
        if other_marketing:
            warnings.append("Marketing expenses from non-Meta sources are reported separately and are not added to Meta spend.")

        spend = _sum(list(selected_daily_spend.values()))
        if not selected_daily_spend:
            spend = None
        impressions = _sum([_decimal(row.impressions) for row in stats])
        reach = _sum([_decimal(row.reach) for row in stats])
        clicks = _sum([_decimal(row.clicks) for row in stats])
        link_clicks = _sum([_decimal(row.link_clicks) for row in stats])
        leads = _sum([_decimal(row.leads) for row in stats])
        messages = _sum([_decimal(row.instagram_messages) for row in stats])

        ctr = _rate(clicks, impressions, Decimal("100"))
        cpc = _rate(spend, clicks)
        cpm = _rate(spend, impressions, Decimal("1000"))
        # Account-level daily rows do not contain purchase counts or conversion value.
        cpa = None
        roas = None
        warnings.append("Account-level stored statistics do not include purchase conversion count/value; CPA and ROAS are unavailable.")
        if impressions == 0:
            warnings.append("CTR and CPM are unavailable because impressions are zero.")
        if clicks == 0:
            warnings.append("CPC is unavailable because clicks are zero.")

        profitability = DeterministicProfitabilityService.overall(
            db, business_id, start_date, end_date
        )
        meta_spend_not_in_ledger = (
            spend is not None and spend > 0 and not meta_expenses
        )
        if meta_spend_not_in_ledger:
            warnings.append("The business-profit estimate may exclude Meta spend because Meta daily statistics are not automatically included in the expense ledger.")

        return MarketingOverview(
            business_id=business_id,
            start_date=start_date,
            end_date=end_date,
            spend=_metric(spend, "MetaDailyStats.spend preferred; Meta-source Expense fallback by date"),
            meta_expense_ledger_spend=_metric(meta_ledger_total, "Expense.source=meta"),
            other_marketing_expenses=_metric(other_marketing_total, "marketing Expense rows whose source is not meta", "Kept separate; not included in Meta spend."),
            meta_ledger_overlap_amount=_metric(_sum(overlap_values) if overlap_values else Decimal("0"), "MetaDailyStats/Meta Expense date overlap", "Overlap is disclosed and not added twice."),
            overlap_days=overlap_days,
            impressions=_metric(impressions, "MetaDailyStats.impressions"),
            reach=_metric(reach, "MetaDailyStats.reach", "Sum of daily reach; people may be counted on multiple days."),
            clicks=_metric(clicks, "MetaDailyStats.clicks"),
            link_clicks=_metric(link_clicks, "MetaDailyStats.link_clicks"),
            leads=_metric(leads, "MetaDailyStats.leads", "Meta-reported action count; not a purchase conversion."),
            instagram_messages=_metric(messages, "MetaDailyStats.instagram_messages", "Meta-reported action count; not a purchase conversion."),
            attributed_purchase_count=_metric(None, None, "Purchase actions are not persisted in MetaDailyStats."),
            attributed_conversion_value=_metric(None, None, PURCHASE_VALUE_UNAVAILABLE),
            observed_business_revenue=_metric(
                profitability.net_revenue.amount,
                "DeterministicProfitabilityService: delivered business orders",
                "Observed business revenue is not attributed to Meta or any campaign.",
            ),
            observed_business_profit_estimate=_metric(
                profitability.net_profit.amount,
                "DeterministicProfitabilityService",
                "Business-wide estimate, not campaign-attributed; see profitability completeness warnings.",
            ),
            observed_revenue_attribution_note="Observed order revenue is business-wide and must not be interpreted as Meta-attributed revenue.",
            ctr_percent=ctr,
            cpc=cpc,
            cpm=cpm,
            cpa=cpa,
            roas=roas,
            warnings=warnings,
        )

    @staticmethod
    def trends(db: Session, business_id: int, start_date=None, end_date=None) -> MarketingTrendResponse:
        MarketingIntelligenceService._validate_period(start_date, end_date)
        query = db.query(MetaDailyStats).filter(MetaDailyStats.business_id == business_id)
        query = _date_filters(query, MetaDailyStats.stats_date, start_date, end_date)
        rows = query.order_by(MetaDailyStats.stats_date).all()
        points = []
        for row in rows:
            spend = _decimal(row.spend)
            impressions = _decimal(row.impressions)
            clicks = _decimal(row.clicks)
            points.append(MarketingTrendPoint(
                stats_date=row.stats_date,
                spend=_metric(spend, "MetaDailyStats.spend"),
                impressions=_metric(impressions, "MetaDailyStats.impressions"),
                clicks=_metric(clicks, "MetaDailyStats.clicks"),
                ctr_percent=_rate(clicks, impressions, Decimal("100")),
                cpc=_rate(spend, clicks),
                cpm=_rate(spend, impressions, Decimal("1000")),
            ))
        warnings = [] if rows else ["No stored Meta daily statistics exist for this period; no trend is inferred from campaign snapshots."]
        return MarketingTrendResponse(
            business_id=business_id, start_date=start_date, end_date=end_date,
            points=points, warnings=warnings,
        )

    @staticmethod
    def _provider_data(db, business_id, level, start_date, end_date):
        settings = db.query(SettingsModel).filter(SettingsModel.business_id == business_id).first()
        if not settings or not settings.meta_account_id or not settings.meta_access_token:
            return None, "Meta campaign data is unavailable because this business has no configured Meta connection."
        provider = {
            "campaign": (MetaAdsService.get_campaigns, "campaigns"),
            "adset": (MetaAdsService.get_adsets, "adsets"),
            "ad": (MetaAdsService.get_ads, "ads"),
        }
        method, key = provider[level]
        try:
            response = method(db, start_date.isoformat() if start_date else None, end_date.isoformat() if end_date else None)
        except Exception:
            return None, "Meta campaign data could not be retrieved."
        if not isinstance(response, dict) or response.get("success") is not True:
            return None, "Meta campaign data could not be retrieved; provider details are withheld."
        return response.get(key, []), None

    @classmethod
    def _entities(cls, rows, level, previous_rows=None):
        previous_by_id = {
            str(row.get(f"{level}_id") or ""): row
            for row in (previous_rows or [])
        }
        normalized = []
        warnings = []
        for row in rows:
            entity_id = str(row.get(f"{level}_id") or "").strip()
            if not entity_id:
                warnings.append("A Meta insight row without a stable entity ID was omitted.")
                continue
            spend = _decimal(row.get("spend"))
            impressions = _decimal(row.get("impressions"))
            reach = _decimal(row.get("reach"))
            clicks = _decimal(row.get("clicks"))
            link_clicks = _decimal(row.get("link_clicks"))
            reported_purchases = row.get("purchase_data_available") is True
            conversions = _decimal(row.get("sales")) if reported_purchases else None
            leads = _decimal(row.get("leads"))
            messages = _decimal(row.get("instagram_messages"))
            ctr = _rate(clicks, impressions, Decimal("100"))
            cpc = _rate(spend, clicks)
            cpm = _rate(spend, impressions, Decimal("1000"))
            cpa = _rate(spend, conversions) if conversions and conversions > 0 else None
            # Conversion value is not returned or persisted by current Meta services.
            roas = None
            prev = previous_by_id.get(entity_id)
            spend_change = ctr_change = None
            unusual = False
            prev_spend = _decimal(prev.get("spend")) if prev else None
            prev_impressions = _decimal(prev.get("impressions")) if prev else None
            prev_clicks = _decimal(prev.get("clicks")) if prev else None
            prev_ctr = _rate(prev_clicks, prev_impressions, Decimal("100"))
            if prev and prev_spend is not None and prev_spend > 0 and spend is not None and spend >= MIN_CONCLUSION_SPEND and prev_spend >= MIN_CONCLUSION_SPEND and impressions is not None and impressions >= MIN_CONCLUSION_IMPRESSIONS and prev_impressions is not None and prev_impressions >= MIN_CONCLUSION_IMPRESSIONS:
                spend_change_decimal = (spend - prev_spend) / prev_spend * 100
                spend_change = float(spend_change_decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                unusual = abs(spend_change_decimal) >= UNUSUAL_CHANGE_PERCENT
            if ctr is not None and prev_ctr is not None and prev_ctr > 0 and impressions is not None and impressions >= MIN_CONCLUSION_IMPRESSIONS and prev_impressions is not None and prev_impressions >= MIN_CONCLUSION_IMPRESSIONS:
                ctr_change = float(((Decimal(str(ctr)) - Decimal(str(prev_ctr))) / Decimal(str(prev_ctr)) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            enough_data = bool(spend is not None and spend >= MIN_CONCLUSION_SPEND and impressions is not None and impressions >= MIN_CONCLUSION_IMPRESSIONS)
            recs = []
            entity_name = row.get(f"{level}_name")
            if enough_data and conversions == 0 and reported_purchases:
                recs.append("Review purchase-tracking coverage and campaign landing experience; Meta reported spend but no purchase actions for this period.")
            elif enough_data and not reported_purchases:
                recs.append("Verify Meta purchase-event reporting; the provider returned no purchase action count for this campaign.")
            normalized.append((row, entity_id, entity_name, spend, impressions, reach, clicks, link_clicks, conversions, reported_purchases, leads, messages, ctr, cpc, cpm, cpa, roas, spend_change, ctr_change, unusual, enough_data, recs))

        eligible_cpcs = [entry[13] for entry in normalized if entry[20] and entry[6] is not None and entry[6] >= MIN_CPC_CLICKS and entry[13] is not None]
        eligible_cpcs.sort()
        median_cpc = eligible_cpcs[len(eligible_cpcs) // 2] if eligible_cpcs else None
        results = []
        for entry in normalized:
            (row, entity_id, name, spend, impressions, reach, clicks, link_clicks, conversions, conversions_available, leads, messages, ctr, cpc, cpm, cpa, roas, spend_change, ctr_change, unusual, enough_data, recs) = entry
            if median_cpc is not None and enough_data and clicks is not None and clicks >= MIN_CPC_CLICKS and cpc is not None and cpc > median_cpc * 1.5:
                recs.append("Investigate this entity's CPC; it is more than 1.5 times the eligible campaign median.")
            if ctr_change is not None and ctr_change <= -30:
                recs.append("Review the CTR decline against the previous period; impressions are sufficient in both periods.")
            if unusual:
                direction = "increased" if spend_change and spend_change > 0 else "decreased"
                recs.append(f"Review why spend {direction} by at least 50% versus the previous period; the comparison met the minimum data threshold.")
            entity_warnings = []
            if not enough_data:
                entity_warnings.append("Insufficient data for performance conclusions; minimums are spend >= 10 and impressions >= 100.")
            entity_warnings.append(PURCHASE_VALUE_UNAVAILABLE)
            entity_warnings.append("Meta-reported purchases are attributed actions, not independently verified business orders or revenue.")
            results.append(MarketingEntityPerformance(
                level=level,
                entity_id=entity_id,
                entity_name=name,
                campaign_id=str(row.get("campaign_id")) if row.get("campaign_id") is not None else None,
                campaign_name=row.get("campaign_name"),
                adset_id=str(row.get("adset_id")) if row.get("adset_id") is not None else None,
                adset_name=row.get("adset_name"),
                ad_id=str(row.get("ad_id")) if row.get("ad_id") is not None else None,
                ad_name=row.get("ad_name"),
                spend=_metric(spend, "Meta-reported campaign insights"),
                impressions=_metric(impressions, "Meta-reported campaign insights"),
                reach=_metric(reach, "Meta-reported campaign insights"),
                clicks=_metric(clicks, "Meta-reported campaign insights"),
                link_clicks=_metric(link_clicks, "Meta-reported link_click action"),
                attributed_purchase_count=_metric(conversions, "Meta-reported purchase action" if conversions_available else None, "Purchase action count is unavailable if the provider omitted purchase actions."),
                attributed_conversion_value=_metric(None, None, PURCHASE_VALUE_UNAVAILABLE),
                leads=_metric(leads, "Meta-reported lead action"),
                instagram_messages=_metric(messages, "Meta-reported messaging actions"),
                ctr_percent=ctr, cpc=cpc, cpm=cpm, cpa=cpa, roas=roas,
                previous_spend_change_percent=spend_change,
                previous_ctr_change_percent=ctr_change,
                unusual_spend_change=unusual,
                sufficient_data_for_conclusions=enough_data,
                recommendations=recs,
                warnings=entity_warnings,
            ))
        return results, warnings

    @classmethod
    def campaigns(cls, db: Session, business_id: int, start_date=None, end_date=None, *, level="campaign", page=1, page_size=25) -> MarketingCampaignPage:
        cls._validate_period(start_date, end_date)
        if level not in {"campaign", "adset", "ad"}:
            raise ValueError("level must be campaign, adset, or ad.")
        current_rows, provider_warning = cls._provider_data(db, business_id, level, start_date, end_date)
        if current_rows is None:
            current_rows = []
        previous_rows = None
        if start_date and end_date:
            days = (end_date - start_date).days + 1
            prev_end = start_date - timedelta(days=1)
            prev_start = prev_end - timedelta(days=days - 1)
            previous_rows, _ = cls._provider_data(db, business_id, level, prev_start, prev_end)
        entities, warnings = cls._entities(current_rows, level, previous_rows or [])
        entities.sort(key=lambda item: (item.spend.amount is not None, item.spend.amount or 0), reverse=True)
        ranked = [item for item in entities if item.sufficient_data_for_conclusions and item.cpa is not None]
        ranked.sort(key=lambda item: item.cpa)
        best = ranked[0].entity_id if ranked else None
        worst = ranked[-1].entity_id if ranked else None
        if not current_rows and provider_warning is None:
            warnings.append("Meta returned no entity rows for this period.")
        if provider_warning:
            warnings.append(provider_warning)
        warnings.append("Conversion value is unavailable, so ROAS and campaign-attributed profit cannot be calculated.")
        offset = (page - 1) * page_size
        return MarketingCampaignPage(
            business_id=business_id, level=level, start_date=start_date, end_date=end_date,
            total=len(entities), page=page, page_size=page_size,
            best_performing_entity_id=best, worst_performing_entity_id=worst,
            campaigns=entities[offset:offset + page_size], warnings=warnings,
        )

    @classmethod
    def campaign_detail(cls, db: Session, business_id: int, campaign_id: str, start_date=None, end_date=None):
        cls._validate_period(start_date, end_date)
        campaign_rows, campaign_warning = cls._provider_data(
            db, business_id, "campaign", start_date, end_date
        )
        campaign_entities, _ = cls._entities(campaign_rows or [], "campaign")
        campaign = next((item for item in campaign_entities if item.entity_id == str(campaign_id)), None)
        if campaign is None:
            return None
        adsets, adset_warning = cls._provider_data(db, business_id, "adset", start_date, end_date)
        ads, ad_warning = cls._provider_data(db, business_id, "ad", start_date, end_date)
        adset_entities, _ = cls._entities(
            [row for row in (adsets or []) if str(row.get("campaign_id")) == str(campaign_id)],
            "adset",
        )
        ad_entities, _ = cls._entities(
            [row for row in (ads or []) if str(row.get("campaign_id")) == str(campaign_id)],
            "ad",
        )
        warnings = []
        if campaign_warning:
            warnings.append(campaign_warning)
        warnings.extend(warning for warning in (adset_warning, ad_warning) if warning)
        return MarketingCampaignDetail(
            business_id=business_id, campaign=campaign,
            adsets=adset_entities, ads=ad_entities, warnings=warnings,
        )
