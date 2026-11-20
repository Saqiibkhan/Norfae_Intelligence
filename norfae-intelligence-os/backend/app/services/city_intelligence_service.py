from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.order_model import Order
from app.schemas.intelligence_schema import (
    CityIntelligenceItem,
    CityIntelligencePage,
    ProfitabilityComponent,
)
from app.services.deterministic_profitability_service import DeterministicProfitabilityService


def _amount(value):
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
        return parsed if parsed.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _sum_values(values, *, empty_zero=False):
    if not values:
        return Decimal("0") if empty_zero else None
    if any(value is None for value in values):
        return None
    return sum(values, Decimal("0"))


def _component(value, source, note=None):
    return ProfitabilityComponent(
        amount=float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if value is not None else None,
        available=value is not None,
        source=source,
        note=note,
    )


class CityIntelligenceService:

    @staticmethod
    def analyze_business(
        db: Session,
        business_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> CityIntelligencePage:
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must be on or before end_date.")
        business_date = func.coalesce(Order.confirmed_order_date, Order.discord_created_at, Order.created_at)

        def load(period_start=None, period_end=None):
            query = db.query(Order).filter(Order.business_id == business_id)
            if period_start:
                query = query.filter(business_date >= datetime.combine(period_start, time.min))
            if period_end:
                query = query.filter(business_date < datetime.combine(period_end + timedelta(days=1), time.min))
            return query.order_by(Order.id).all()

        orders = load(start_date, end_date)
        previous_orders = []
        if start_date and end_date:
            days = (end_date - start_date).days + 1
            previous_end = start_date - timedelta(days=1)
            previous_start = previous_end - timedelta(days=days - 1)
            previous_orders = load(previous_start, previous_end)

        def group_orders(rows):
            groups = defaultdict(list)
            for order in rows:
                city = (order.city or "").strip()
                province = (order.province or "").strip()
                key = (city.casefold() or None, province.casefold() or None)
                groups[key].append(order)
            return groups

        current_groups, prior_groups = group_orders(orders), group_orders(previous_orders)
        metrics = []
        for key, city_orders in current_groups.items():
            delivered = [o for o in city_orders if (o.status or "").upper() == "DELIVERED"]
            cancelled = [o for o in city_orders if (o.status or "").upper() == "CANCELLED"]
            returned = [o for o in city_orders if (o.status or "").upper() == "RETURNED"]
            revenue = _sum_values([_amount(o.selling_price) for o in delivered], empty_zero=not delivered)
            cogs = _sum_values([_amount(o.product_cost) for o in delivered], empty_zero=not delivered)
            contribution, contribution_margin = DeterministicProfitabilityService.product_contribution(
                revenue, cogs, source="delivered order revenue less recorded product cost"
            )
            delivery_costs = _sum_values([_amount(o.delivery_cost) for o in city_orders])
            order_profit_results = [DeterministicProfitabilityService.order_record(o).net_profit for o in delivered]
            order_profit_values = [
                _amount(result.amount) if result.available else None
                for result in order_profit_results
            ]
            estimated_profit = _sum_values(order_profit_values, empty_zero=not delivered)
            total = len(city_orders)
            delivered_count = len(delivered)
            cancellation_rate = round(len(cancelled) / total * 100, 2) if total else None
            return_rate = round(len(returned) / total * 100, 2) if total else None
            average_order_value = (
                float((revenue / delivered_count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                if revenue is not None and delivered_count else None
            )
            delivery_per_delivered = (
                float((delivery_costs / delivered_count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                if delivery_costs is not None and delivered_count else None
            )
            prior = prior_groups.get(key, [])
            prior_delivered = [o for o in prior if (o.status or "").upper() == "DELIVERED"]
            prior_revenue = _sum_values([_amount(o.selling_price) for o in prior_delivered], empty_zero=not prior_delivered)
            change = None
            unusual = False
            if len(delivered) >= 3 and len(prior_delivered) >= 3 and prior_revenue not in (None, Decimal("0")) and revenue is not None:
                change = float(((revenue - prior_revenue) / prior_revenue * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                unusual = abs(change) >= 50
            display_city = next((o.city.strip() for o in city_orders if o.city and o.city.strip()), None)
            display_province = next((o.province.strip() for o in city_orders if o.province and o.province.strip()), None)
            warnings = []
            if display_city is None:
                warnings.append("City is missing; this record is grouped in the Unknown city bucket.")
            if any(o.delivery_cost is None for o in city_orders):
                warnings.append("Some delivery-cost values are unavailable.")
            warnings.append("City contribution excludes delivery, packaging, advertising, and general expenses. Estimated order profit excludes unallocated business expenses and unknown refunds.")
            recommendations = []
            if contribution.amount is None:
                recommendations.append("Complete delivered order revenue and product-cost records before comparing city contribution.")
            elif contribution.amount < 0:
                recommendations.append("Review product mix and recorded product costs for this city; delivered product contribution is negative.")
            if total >= 5 and ((cancellation_rate or 0) + (return_rate or 0)) >= 30:
                recommendations.append("Review delivery and product-related cancellation/return reasons; the combined observed rate is at least 30% on five or more orders.")
            if unusual:
                direction = "increased" if change and change > 0 else "decreased"
                recommendations.append(f"Investigate the {direction} in delivered revenue versus the previous equal-length period; the change exceeded 50% with at least three delivered orders in both periods.")
            if delivery_per_delivered is not None and delivered_count >= 3:
                recommendations.append("Compare recorded delivery cost per delivered order with carrier terms and the city's full contribution; delivery cost is only one part of city economics.")
            metrics.append(CityIntelligenceItem(
                city=display_city, province=display_province,
                total_orders=total, delivered_orders=delivered_count,
                cancelled_orders=len(cancelled), returned_orders=len(returned),
                cancellation_rate_percent=cancellation_rate,
                return_rate_percent=return_rate,
                total_revenue=_component(revenue, "orders.selling_price for delivered orders"),
                average_order_value=average_order_value,
                recorded_delivery_costs=_component(delivery_costs, "orders.delivery_cost for all city orders"),
                delivery_cost_per_delivered_order=delivery_per_delivered,
                product_contribution=contribution,
                contribution_margin_percent=contribution_margin,
                estimated_order_profit=_component(estimated_profit, "sum of deterministic delivered-order estimates", "Excludes unallocated business expenses; excludes cancelled/returned liability."),
                unallocated_business_expenses=ProfitabilityComponent(amount=None, available=False, note="Business expenses cannot be assigned to a city with the current schema."),
                previous_period_revenue_change_percent=change,
                unusual_performance_change=unusual,
                recommendations=recommendations,
                warnings=warnings,
            ))

        ranked = [city for city in metrics if city.delivered_orders and city.product_contribution.available]
        ranked.sort(key=lambda city: (city.product_contribution.amount, city.total_revenue.amount or 0), reverse=True)
        best = ranked[0].city if ranked else None
        lowest = ranked[-1].city if ranked else None
        metrics.sort(key=lambda city: (city.product_contribution.amount is not None, city.product_contribution.amount or 0), reverse=True)
        warnings = []
        if any(city.city is None for city in metrics):
            warnings.append("Orders without city values are included in the Unknown city bucket.")
        if not metrics:
            warnings.append("No orders exist for this business and period.")
        return CityIntelligencePage(
            business_id=business_id, start_date=start_date, end_date=end_date,
            total_cities=len(metrics), best_performing_city=best,
            lowest_performing_city=lowest, cities=metrics, warnings=warnings,
        )

    @staticmethod
    def get_city(db: Session, business_id: int, city_name: str, start_date=None, end_date=None):
        page = CityIntelligenceService.analyze_business(db, business_id, start_date, end_date)
        normalized = city_name.strip().casefold()
        return [city for city in page.cities if (city.city or "unknown").casefold() == normalized]

    @staticmethod
    def get_city_intelligence(db: Session):

        orders = db.query(Order).all()

        cities = defaultdict(
            lambda: {
                "city": "",
                "province": "",
                "orders": 0,
                "delivered": 0,
                "cancelled": 0,
                "returned": 0,
                "revenue": 0,
                "profit": 0,
                "delivery_total": 0,
                "success_rate": 0,
                "loss_rate": 0,
                "profit_margin": 0,
                "avg_delivery_cost": 0,
                "revenue_per_order": 0,
                "profit_per_order": 0,
                "performance_status": "weak",
            }
        )

        for order in orders:

            city = order.city or "Unknown"

            province = order.province or "Unknown"

            key = f"{city}_{province}"

            cities[key]["city"] = city

            cities[key]["province"] = province

            cities[key]["orders"] += 1

            cities[key]["delivery_total"] += float(order.delivery_cost or 0)

            status = (order.status or "").upper()

            if status == "DELIVERED":

                cities[key]["delivered"] += 1

                cities[key]["revenue"] += float(order.selling_price or 0)

                cities[key]["profit"] += float(order.net_profit or 0)

            elif status == "CANCELLED":

                cities[key]["cancelled"] += 1

            elif status == "RETURNED":

                cities[key]["returned"] += 1

        for city in cities.values():

            orders = city["orders"]

            delivered = city["delivered"]

            cancelled = city["cancelled"]

            returned = city["returned"]

            revenue = city["revenue"]

            profit = city["profit"]

            city["success_rate"] = round((delivered / orders) * 100, 2) if orders else 0

            city["loss_rate"] = (
                round(
                    ((cancelled + returned) / orders) * 100,
                    2,
                )
                if orders
                else 0
            )

            city["avg_delivery_cost"] = (
                round(
                    city["delivery_total"] / orders,
                    2,
                )
                if orders
                else 0
            )

            city["profit_margin"] = (
                round(
                    (profit / revenue) * 100,
                    2,
                )
                if revenue
                else 0
            )

            city["revenue_per_order"] = (
                round(revenue / delivered, 2) if delivered else 0
            )

            city["profit_per_order"] = round(profit / delivered, 2) if delivered else 0

            if orders < 5:

                city["performance_status"] = "testing"

            elif city["loss_rate"] >= 40:

                city["performance_status"] = "risky"

            elif city["success_rate"] >= 85:

                city["performance_status"] = "elite"

            elif city["success_rate"] >= 70:

                city["performance_status"] = "strong"

            else:

                city["performance_status"] = "weak"

        return sorted(
            cities.values(),
            key=lambda x: (
                x["profit"],
                x["revenue"],
            ),
            reverse=True,
        )
