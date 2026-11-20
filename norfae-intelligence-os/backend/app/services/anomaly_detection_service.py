from collections import defaultdict
from datetime import date, datetime, time, timedelta
from hashlib import sha256
from math import isfinite

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai_engine.anomaly_detection_engine import (
    AnomalyDetectionEngine,
    AnomalyThresholds,
)
from app.models import Expense, Order
from app.schemas.anomaly_schema import (
    AnomalyCategory,
    AnomalyRecord,
    AnomalyReport,
    AnomalySeverity,
    AnomalySummary,
    AnomalyQuery,
)
from app.services.city_intelligence_service import CityIntelligenceService
from app.services.deterministic_profitability_service import DeterministicProfitabilityService
from app.services.marketing_intelligence_service import MarketingIntelligenceService


class AnomalyDetectionService:
    """Read-only, explainable anomaly detection from dated tenant data."""

    def __init__(self, thresholds: AnomalyThresholds | None = None):
        self.thresholds = thresholds or AnomalyThresholds()

    @staticmethod
    def _finite(value):
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return number if isfinite(number) else None

    @staticmethod
    def _order_day(order: Order) -> date | None:
        value = order.confirmed_order_date or order.discord_created_at or order.created_at
        return value.date() if value else None

    @staticmethod
    def _period(start_date, end_date):
        end = end_date or date.today()
        start = start_date or end - timedelta(days=29)
        if start > end:
            raise ValueError("start_date must be on or before end_date.")
        return start, end

    @staticmethod
    def _anomaly_id(business_id, category, metric_name, period, identity=None):
        raw = f"{business_id}|{category}|{metric_name}|{period.isoformat()}|{identity or ''}"
        return sha256(raw.encode("utf-8")).hexdigest()[:24]

    def _record(
        self,
        business_id: int,
        category: AnomalyCategory,
        metric_name: str,
        observed: float,
        expected: float | None,
        deviation: float | None,
        deviation_percent: float | None,
        method: str,
        period: date,
        explanation: str,
        investigation: str,
        *,
        severity: AnomalySeverity | None = None,
        identity: str | None = None,
    ) -> AnomalyRecord:
        if severity is None:
            magnitude = abs(deviation_percent or 0)
            severity = "high" if magnitude >= self.thresholds.high_severity_percent else "medium"
        return AnomalyRecord(
            anomaly_id=self._anomaly_id(business_id, category, metric_name, period, identity),
            business_id=business_id,
            category=category,
            severity=severity,
            metric_name=metric_name,
            observed_value=round(observed, 4),
            expected_value=round(expected, 4) if expected is not None else None,
            deviation_value=round(deviation, 4) if deviation is not None else None,
            deviation_percent=round(deviation_percent, 2) if deviation_percent is not None else None,
            detection_method=method,
            period_start=period,
            period_end=period,
            explanation=explanation,
            recommended_investigation=investigation,
        )

    def _series_anomalies(
        self,
        business_id: int,
        series: dict[date, float | None],
        *,
        category: AnomalyCategory,
        metric_name: str,
        threshold_percent: float,
        insufficient: set[str],
        investigation: str,
        start_date: date,
        end_date: date,
        minimum_history: int | None = None,
    ) -> list[AnomalyRecord]:
        minimum_history = minimum_history or self.thresholds.min_history_points
        results = []
        history_start = start_date - timedelta(days=self.thresholds.baseline_days)
        for period, observed in sorted(series.items()):
            if period < start_date or period > end_date or observed is None:
                continue
            history = [
                value
                for day, value in series.items()
                if history_start <= day < period and value is not None
            ]
            if len(history) < minimum_history:
                insufficient.add(
                    f"{metric_name} on {period.isoformat()}: requires {minimum_history} prior dated observations; found {len(history)}."
                )
                continue
            comparison = AnomalyDetectionEngine.compare_with_history(
                observed,
                history,
                min_history_points=minimum_history,
                change_threshold_percent=threshold_percent,
                z_score_min_points=self.thresholds.z_score_min_points,
                z_score_threshold=self.thresholds.z_score_threshold,
            )
            if comparison is None:
                continue
            expected = comparison["expected_value"]
            deviation = comparison["deviation_value"]
            deviation_percent = comparison["deviation_percent"]
            direction = "increased" if deviation > 0 else "decreased"
            results.append(self._record(
                business_id,
                category,
                metric_name,
                observed,
                expected,
                deviation,
                deviation_percent,
                comparison["method"],
                period,
                f"{metric_name} {direction} by {abs(deviation_percent):.1f}% versus the mean of {len(history)} prior dated observations.",
                investigation,
            ))
        return results

    def detect(
        self,
        db: Session,
        business_id: int,
        query: AnomalyQuery | None = None,
    ) -> tuple[AnomalyReport, AnomalySummary]:
        query = query or AnomalyQuery()
        start_date, end_date = self._period(query.start_date, query.end_date)
        history_start = start_date - timedelta(days=self.thresholds.baseline_days)
        from_dt = datetime.combine(history_start, time.min)
        to_dt = datetime.combine(end_date + timedelta(days=1), time.min)

        orders = (
            db.query(Order)
            .filter(
                Order.business_id == business_id,
                func.coalesce(
                    Order.confirmed_order_date,
                    Order.discord_created_at,
                    Order.created_at,
                ) >= from_dt,
                func.coalesce(
                    Order.confirmed_order_date,
                    Order.discord_created_at,
                    Order.created_at,
                ) < to_dt,
            )
            .order_by(Order.id)
            .all()
        )
        by_day = defaultdict(list)
        for order in orders:
            day = self._order_day(order)
            if day is not None:
                by_day[day].append(order)

        order_count: dict[date, float | None] = {}
        revenue: dict[date, float | None] = {}
        average_order_value: dict[date, float | None] = {}
        cancellation_rate: dict[date, float | None] = {}
        return_rate: dict[date, float | None] = {}
        delivery_per_delivered: dict[date, float | None] = {}
        for day, day_orders in by_day.items():
            order_count[day] = float(len(day_orders))
            delivered = [order for order in day_orders if (order.status or "").upper() == "DELIVERED"]
            cancelled = [order for order in day_orders if (order.status or "").upper() == "CANCELLED"]
            returned = [order for order in day_orders if (order.status or "").upper() == "RETURNED"]
            if delivered and all(order.selling_price is not None for order in delivered):
                daily_revenue = sum(float(order.selling_price) for order in delivered)
                revenue[day] = daily_revenue
                if len(delivered) >= self.thresholds.min_delivered_orders_for_average:
                    average_order_value[day] = daily_revenue / len(delivered)
                else:
                    average_order_value[day] = None
            else:
                revenue[day] = None
                average_order_value[day] = None
            if len(day_orders) >= self.thresholds.min_orders_for_cancellation_rate:
                cancellation_rate[day] = len(cancelled) / len(day_orders) * 100
                return_rate[day] = len(returned) / len(day_orders) * 100
            else:
                cancellation_rate[day] = None
                return_rate[day] = None
            if len(delivered) >= self.thresholds.min_delivered_orders_for_average and all(
                order.delivery_cost is not None for order in delivered
            ):
                delivery_per_delivered[day] = sum(
                    float(order.delivery_cost) for order in delivered
                ) / len(delivered)
            else:
                delivery_per_delivered[day] = None

        anomalies: list[AnomalyRecord] = []
        insufficient: set[str] = set()
        warnings = [
            "Only dates with source rows are analyzed. Missing dates are not treated as zero because source completeness is not tracked.",
            "Order financial columns have zero defaults; a recorded zero can be indistinguishable from a cost or revenue that was never entered.",
            "Results identify unusual measured values; explanations and investigation steps are suggestions, not causes or automatic actions.",
            "No seasonal adjustment is applied; the available analysis uses a short trailing baseline and does not establish seasonal patterns.",
        ]
        if not by_day:
            insufficient.add("Sales and operations: no dated order observations are available in the analysis window.")
        anomalies.extend(self._series_anomalies(
            business_id, order_count, category="sales", metric_name="daily_order_count",
            threshold_percent=self.thresholds.order_volume_change_percent,
            insufficient=insufficient, investigation="Check order ingestion, campaign/calendar changes, and fulfillment records for this date.",
            start_date=start_date, end_date=end_date,
        ))
        anomalies.extend(self._series_anomalies(
            business_id, revenue, category="sales", metric_name="daily_delivered_revenue",
            threshold_percent=self.thresholds.revenue_change_percent,
            insufficient=insufficient, investigation="Review delivered orders, recorded selling prices, cancellations, and source sync completeness.",
            start_date=start_date, end_date=end_date,
        ))
        anomalies.extend(self._series_anomalies(
            business_id, average_order_value, category="sales", metric_name="daily_average_order_value",
            threshold_percent=self.thresholds.average_order_value_change_percent,
            insufficient=insufficient, investigation="Review the delivered order mix and recorded selling prices for this date.",
            start_date=start_date, end_date=end_date,
        ))
        anomalies.extend(self._series_anomalies(
            business_id, delivery_per_delivered, category="cost", metric_name="delivery_cost_per_delivered_order",
            threshold_percent=self.thresholds.cost_change_percent,
            insufficient=insufficient, investigation="Check recorded carrier charges, destination mix, and order recalculations.",
            start_date=start_date, end_date=end_date,
        ))

        self._add_status_rate_anomalies(
            business_id, cancellation_rate, anomalies, insufficient, start_date, end_date,
            metric_name="daily_cancellation_rate_percent", status_label="cancellation",
        )
        self._add_status_rate_anomalies(
            business_id, return_rate, anomalies, insufficient, start_date, end_date,
            metric_name="daily_return_rate_percent", status_label="return",
        )
        self._add_expense_anomalies(
            db, business_id, anomalies, insufficient, start_date, end_date, history_start, end_date
        )
        self._add_marketing_anomalies(
            db, business_id, anomalies, insufficient, start_date, end_date, history_start
        )
        self._add_product_contribution_anomalies(
            db, business_id, anomalies, insufficient, start_date, end_date
        )
        self._add_city_anomalies(
            db, business_id, anomalies, insufficient, start_date, end_date
        )

        # Deterministic IDs make duplicate findings collapse without persistence.
        unique = {item.anomaly_id: item for item in anomalies}
        filtered = list(unique.values())
        if query.category:
            filtered = [item for item in filtered if item.category == query.category]
        if query.severity:
            filtered = [item for item in filtered if item.severity == query.severity]
        filtered.sort(key=lambda item: (
            item.period_start,
            item.severity == "high",
            item.category,
            item.metric_name,
            item.anomaly_id,
        ), reverse=True)

        report = AnomalyReport(
            business_id=business_id,
            start_date=start_date,
            end_date=end_date,
            total=len(filtered),
            page=query.page,
            page_size=query.page_size,
            anomalies=filtered[(query.page - 1) * query.page_size : query.page * query.page_size],
            insufficient_data=sorted(insufficient),
            warnings=warnings,
        )
        summary = AnomalySummary(
            business_id=business_id,
            start_date=start_date,
            end_date=end_date,
            total=len(filtered),
            by_category=self._count_by(filtered, "category"),
            by_severity=self._count_by(filtered, "severity"),
            insufficient_data=sorted(insufficient),
            warnings=warnings,
        )
        return report, summary

    def _add_status_rate_anomalies(
        self, business_id, series, anomalies, insufficient, start, end,
        *, metric_name: str, status_label: str,
    ):
        baseline_start = start - timedelta(days=self.thresholds.baseline_days)
        for period, observed in sorted(series.items()):
            if not start <= period <= end or observed is None:
                continue
            history = [
                value for day, value in series.items()
                if baseline_start <= day < period and value is not None
            ]
            if len(history) < self.thresholds.min_history_points:
                insufficient.add(
                    f"{metric_name} on {period.isoformat()}: requires {self.thresholds.min_history_points} prior dated observations with at least {self.thresholds.min_orders_for_cancellation_rate} orders each; found {len(history)}."
                )
                continue
            expected = sum(history) / len(history)
            points = observed - expected
            if points >= self.thresholds.cancellation_rate_change_points:
                anomalies.append(self._record(
                    business_id, "operations", metric_name,
                    observed, expected, points, None,
                    "historical_mean_percentage_point_change", period,
                    f"Recorded {status_label} rate increased by {points:.1f} percentage points versus {len(history)} prior observed days.",
                    f"Review {status_label} reasons, order sources, and status update accuracy.",
                    severity="high" if points >= 30 else "medium",
                ))

    def _add_expense_anomalies(self, db, business_id, anomalies, insufficient, start, end, history_start, _end):
        query = db.query(Expense).filter(
            Expense.business_id == business_id,
            Expense.expense_date >= datetime.combine(history_start, time.min),
            Expense.expense_date < datetime.combine(end + timedelta(days=1), time.min),
        )
        rows = query.order_by(Expense.id).all()
        daily = defaultdict(list)
        for row in rows:
            category = (row.category or "").strip().casefold()
            if category in {"marketing", "advertising"}:
                continue
            if row.expense_date:
                daily[row.expense_date.date()].append(self._finite(row.amount))
        series = {
            day: (sum(values) if values and all(value is not None for value in values) else None)
            for day, values in daily.items()
        }
        anomalies.extend(self._series_anomalies(
            business_id, series, category="cost", metric_name="daily_non_marketing_expenses",
            threshold_percent=self.thresholds.cost_change_percent,
            insufficient=insufficient, investigation="Verify expense categorization, duplicate entries, and supporting invoices.",
            start_date=start, end_date=end,
        ))

    def _add_marketing_anomalies(self, db, business_id, anomalies, insufficient, start, end, history_start):
        trends = MarketingIntelligenceService.trends(db, business_id, history_start, end)
        metric_fields = (
            ("spend", "daily_meta_ad_spend", self.thresholds.marketing_spend_change_percent,
             "marketing", "Check Meta spend reports and confirm that synced expenses are not duplicated."),
            ("ctr_percent", "daily_meta_ctr_percent", self.thresholds.marketing_rate_change_percent,
             "marketing", "Review impression/click counts and campaign delivery changes."),
            ("cpc", "daily_meta_cpc", self.thresholds.marketing_rate_change_percent,
             "marketing", "Review clicks, spend, and Meta reporting for this day."),
            ("cpm", "daily_meta_cpm", self.thresholds.marketing_rate_change_percent,
             "marketing", "Review impression volume, spend, and delivery mix for this day."),
        )
        for field, metric_name, threshold, category, investigation in metric_fields:
            series = {}
            for point in trends.points:
                metric = getattr(point, field) if field == "spend" else None
                if metric is not None:
                    series[point.stats_date] = metric.amount if metric.available else None
                else:
                    series[point.stats_date] = getattr(point, field)
            anomalies.extend(self._series_anomalies(
                business_id, series, category=category, metric_name=metric_name,
                threshold_percent=threshold, insufficient=insufficient,
                investigation=investigation, start_date=start, end_date=end,
            ))
        if not trends.points:
            insufficient.add("Marketing anomalies: no stored Meta daily-stat observations are available; no live Meta request was made.")

    def _add_product_contribution_anomalies(self, db, business_id, anomalies, insufficient, start, end):
        current = DeterministicProfitabilityService.products(db, business_id, start, end)
        previous_days = (end - start).days + 1
        previous_end = start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=previous_days - 1)
        previous = DeterministicProfitabilityService.products(
            db, business_id, previous_start, previous_end
        )
        prior_by_key = {row.product_key: row for row in previous}
        minimum = self.thresholds.min_units_for_product_contribution
        for row in current:
            if row.units_sold < minimum or not row.contribution_profit.available:
                if row.units_sold and row.units_sold < minimum:
                    insufficient.add(
                        f"Product contribution for {row.product_key}: requires at least {minimum} delivered units; found {row.units_sold}."
                    )
                continue
            amount = row.contribution_profit.amount
            prior = prior_by_key.get(row.product_key)
            if amount is not None and amount < 0:
                anomalies.append(self._record(
                    business_id, "profitability", "product_contribution",
                    amount, 0.0, amount, None, "negative_recorded_product_contribution",
                    end,
                    f"Product {row.product_key} has negative recorded contribution over the selected period.",
                    "Review recorded item prices/costs, discounts, fulfillment charges, and SKU matching.",
                    severity="high",
                    identity=row.product_key,
                ))
            if (
                prior is not None
                and prior.units_sold >= minimum
                and prior.contribution_profit.available
                and prior.contribution_profit.amount is not None
                and prior.contribution_profit.amount > 0
                and amount is not None
                and (prior.contribution_profit.amount - amount)
                / prior.contribution_profit.amount * 100
                >= self.thresholds.revenue_change_percent
            ):
                expected = prior.contribution_profit.amount
                change = (amount - expected) / expected * 100
                anomalies.append(self._record(
                    business_id, "profitability", "product_contribution_change",
                    amount, expected, amount - expected, change,
                    "equal_length_period_contribution_comparison", end,
                    f"Product {row.product_key} contribution declined by {abs(change):.1f}% versus the preceding equal-length period.",
                    "Check product cost updates, selling price, discounts, returns, and item matching.",
                    identity=row.product_key,
                ))

    def _add_city_anomalies(self, db, business_id, anomalies, insufficient, start, end):
        page = CityIntelligenceService.analyze_business(db, business_id, start, end)
        for city in page.cities:
            change = city.previous_period_revenue_change_percent
            if change is None:
                if city.delivered_orders:
                    insufficient.add(
                        f"City revenue change for {city.city or 'Unknown'}: requires at least {self.thresholds.min_delivered_orders_for_city} delivered orders in both equal-length periods."
                    )
                continue
            if abs(change) < self.thresholds.revenue_change_percent:
                continue
            observed = city.total_revenue.amount
            if observed is None:
                continue
            expected = observed / (1 + change / 100) if change > -100 else None
            direction = "increased" if change > 0 else "decreased"
            anomalies.append(self._record(
                business_id, "operations", "city_delivered_revenue_change",
                observed, expected, observed - expected if expected is not None else None,
                change, "equal_length_period_city_comparison", end,
                f"Delivered revenue for {city.city or 'Unknown'} {direction} by {abs(change):.1f}% versus the previous equal-length period.",
                "Review order volume, city normalization, delivery coverage, and period data completeness.",
                identity=f"{city.city or 'Unknown'}|{city.province or 'Unknown'}",
            ))

    @staticmethod
    def _count_by(anomalies, field):
        counts = defaultdict(int)
        for anomaly in anomalies:
            counts[getattr(anomaly, field)] += 1
        return dict(sorted(counts.items()))

    def list_anomalies(self, db, business_id, query=None):
        return self.detect(db, business_id, query)[0]

    def summary(self, db, business_id, query=None):
        return self.detect(db, business_id, query)[1]

    def get_anomaly(self, db, business_id, anomaly_id, query=None):
        # Detail lookup ignores pagination but preserves period/category/severity filters.
        query = query or AnomalyQuery()
        query = query.model_copy(update={"page": 1, "page_size": 100})
        report, _ = self.detect(db, business_id, query)
        if report.total > len(report.anomalies):
            for page in range(2, (report.total + 99) // 100 + 1):
                next_query = query.model_copy(update={"page": page})
                next_report, _ = self.detect(db, business_id, next_query)
                report.anomalies.extend(next_report.anomalies)
        return next((item for item in report.anomalies if item.anomaly_id == anomaly_id), None)
