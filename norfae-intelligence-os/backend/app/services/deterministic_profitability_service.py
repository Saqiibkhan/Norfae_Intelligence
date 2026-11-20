from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Expense, Order, OrderItem
from app.schemas.intelligence_schema import (
    OrderProfitability,
    ProductProfitability,
    ProfitabilityComponent,
    ProfitabilitySummary,
)

CENT = Decimal("0.01")
DELIVERED = "DELIVERED"
CANCELLED = "CANCELLED"
RETURNED = "RETURNED"


def _decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _rounded(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(CENT, rounding=ROUND_HALF_UP))


def _sum_known(values: list[Decimal | None]) -> Decimal | None:
    if not values or any(value is None for value in values):
        return None
    return sum(values, Decimal("0"))


def _component(value: Decimal | None, source: str | None, note: str | None = None):
    return ProfitabilityComponent(
        amount=_rounded(value), available=value is not None, source=source, note=note
    )


class DeterministicProfitabilityService:
    """Transparent calculations over recorded values; this service never writes."""

    @staticmethod
    def _orders(db: Session, business_id: int, start_date=None, end_date=None):
        query = db.query(Order).filter(Order.business_id == business_id)
        business_date = func.coalesce(
            Order.confirmed_order_date, Order.discord_created_at, Order.created_at
        )
        if start_date:
            query = query.filter(business_date >= datetime.combine(start_date, time.min))
        if end_date:
            next_day = end_date + timedelta(days=1)
            query = query.filter(business_date < datetime.combine(next_day, time.min))
        return query.order_by(Order.id).all()

    @classmethod
    def overall(cls, db: Session, business_id: int, start_date=None, end_date=None) -> ProfitabilitySummary:
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must be on or before end_date.")
        orders = cls._orders(db, business_id, start_date, end_date)
        delivered = [o for o in orders if (o.status or "").upper() == DELIVERED]
        cancelled = [o for o in orders if (o.status or "").upper() == CANCELLED]
        returned = [o for o in orders if (o.status or "").upper() == RETURNED]
        other = [o for o in orders if (o.status or "").upper() not in {DELIVERED, CANCELLED, RETURNED}]
        warnings = [
            "The schema has no original/list-price field; gross revenue before discounts is unavailable.",
            "The schema has no discount or refund amount fields; those amounts cannot be calculated.",
            "Returned and cancelled order liabilities are not included because refund, recovery, and incurred-cost fields are absent.",
        ]

        revenue_values = [_decimal(o.selling_price) for o in delivered]
        revenue = _sum_known(revenue_values)
        cogs = _sum_known([_decimal(o.product_cost) for o in delivered])
        packaging = _sum_known([_decimal(o.packaging_cost) for o in delivered])
        delivery = _sum_known([_decimal(o.delivery_cost) for o in delivered])
        per_order_ads = _sum_known([_decimal(o.marketing_cost) for o in delivered])
        direct_other = _sum_known([_decimal(o.other_expense) for o in delivered])

        expenses_query = db.query(Expense).filter(Expense.business_id == business_id)
        if start_date:
            expenses_query = expenses_query.filter(Expense.expense_date >= datetime.combine(start_date, time.min))
        if end_date:
            next_day = end_date + timedelta(days=1)
            expenses_query = expenses_query.filter(Expense.expense_date < datetime.combine(next_day, time.min))
        expenses = expenses_query.order_by(Expense.id).all()
        marketing_expenses = [e for e in expenses if (e.category or "").strip().casefold() in {"marketing", "advertising"}]
        other_expenses = [e for e in expenses if e not in marketing_expenses]
        marketing_values = [_decimal(e.amount) for e in marketing_expenses]
        other_expense_values = [_decimal(e.amount) for e in other_expenses]
        other_expenses_total = _sum_known(other_expense_values) if other_expenses else Decimal("0")

        # Prefer business expense ledger advertising rows, otherwise use the per-order
        # marketing_cost field. Never add MetaDailyStats.spend as it may mirror the ledger.
        if marketing_expenses:
            advertising = _sum_known(marketing_values)
            advertising_source = "expenses(category=marketing|advertising)"
            if per_order_ads not in (None, Decimal("0")):
                warnings.append("Both expense-ledger advertising and per-order marketing values exist; only ledger advertising is counted to avoid likely double-counting.")
        else:
            advertising = per_order_ads
            advertising_source = "orders.marketing_cost"

        # Add order-level other_expense to the business-expense ledger. No input
        # source is silently counted twice: order marketing is excluded above when
        # there are categorized advertising expense rows.
        has_order_other = bool(direct_other and direct_other != 0)
        has_ledger_other = bool(other_expenses_total and other_expenses_total != 0)
        if has_order_other and has_ledger_other:
            total_other = None
            warnings.append("Both per-order other_expense and non-marketing expense-ledger amounts are non-zero; overlap cannot be ruled out, so combined other expense and net profit are unavailable.")
        elif direct_other is None or other_expenses_total is None:
            total_other = None
        else:
            total_other = direct_other + other_expenses_total
        direct_cost_values = (cogs, packaging, delivery, total_other, advertising)
        observed_profit = None
        if revenue is not None and all(value is not None for value in direct_cost_values):
            observed_profit = revenue - sum(direct_cost_values, Decimal("0"))

        if not delivered:
            warnings.append("No delivered orders are in the selected period; revenue and order cost totals are unavailable rather than assumed to be zero.")
        if any(value is None for value in (cogs, packaging, delivery, total_other, advertising)):
            warnings.append("At least one required cost input is null or unavailable; complete profit cannot be calculated.")
        if returned or cancelled:
            warnings.append("Returned/cancelled orders exist; reported profit excludes their unknown refunds and unrecovered costs.")

        margin = None
        if observed_profit is not None and revenue not in (None, Decimal("0")):
            margin = _rounded(observed_profit / revenue * Decimal("100"))
        # The existing schema has no explicit discount/refund fields, so this
        # endpoint cannot certify a complete realized-profit figure.
        complete = False

        return ProfitabilitySummary(
            business_id=business_id,
            start_date=start_date,
            end_date=end_date,
            orders_inspected=len(orders),
            delivered_orders=len(delivered),
            cancelled_orders=len(cancelled),
            returned_orders=len(returned),
            other_status_orders=len(other),
            gross_revenue=_component(None, None, "No list-price field exists."),
            discounts=_component(None, None, "No discount amount field exists."),
            refunds=_component(None, None, "No refund amount field exists."),
            net_revenue=_component(revenue, "orders.selling_price for delivered orders", "Recorded selling_price is treated as recognized order revenue; discount/refund reconciliation is unavailable."),
            cost_of_goods_sold=_component(cogs, "orders.product_cost for delivered orders"),
            packaging_cost=_component(packaging, "orders.packaging_cost for delivered orders"),
            delivery_cost=_component(delivery, "orders.delivery_cost for delivered orders"),
            advertising_expense=_component(advertising, advertising_source, "Marketing expense ledger is preferred; per-order marketing_cost is fallback. MetaDailyStats.spend is intentionally excluded to avoid possible duplicate spend."),
            other_business_expenses=_component(total_other, "orders.other_expense + non-marketing expenses"),
            net_profit=_component(observed_profit, "recorded delivered-order revenue less recorded costs", "Observed estimate; not complete where discounts, refunds, returns, cancellations, or costs are unrecorded."),
            profit_margin_percent=margin,
            complete=complete,
            warnings=warnings,
        )

    @staticmethod
    def product_contribution(revenue, cogs, *, source: str = "recorded revenue less recorded product cost"):
        """Shared contribution formula used for product and city aggregation."""
        revenue_value, cost_value = _decimal(revenue), _decimal(cogs)
        contribution = (
            revenue_value - cost_value
            if revenue_value is not None and cost_value is not None
            else None
        )
        margin = (
            _rounded(contribution / revenue_value * Decimal("100"))
            if contribution is not None and revenue_value != 0
            else None
        )
        return _component(contribution, source), margin

    @classmethod
    def order(cls, db: Session, business_id: int, order_id: int) -> OrderProfitability | None:
        order = db.query(Order).filter(
            Order.business_id == business_id,
            Order.id == order_id,
        ).first()
        if order is None:
            return None
        return cls.order_record(order)

    @staticmethod
    def order_record(order: Order) -> OrderProfitability:
        """Calculate using an already business-scoped order row."""
        status = (order.status or "").upper()
        warnings = ["Order discounts and refunds are not represented in the current schema."]
        if status != DELIVERED:
            warnings.append("Profit is not calculated for non-delivered orders because refunds and incurred/recovered cost details are unavailable.")
            unavailable = _component(None, None, "Not calculable for this order status with available schema fields.")
            return OrderProfitability(
                order_id=order.id, status=order.status,
                revenue=_component(Decimal("0"), "status policy", "Non-delivered order revenue excluded."),
                discounts=_component(None, None, "No discount field exists."),
                refunds=_component(None, None, "No refund field exists."),
                cost_of_goods_sold=unavailable, packaging_cost=unavailable,
                delivery_cost=unavailable, advertising_cost=unavailable,
                other_order_costs=unavailable, net_profit=unavailable,
                profit_margin_percent=None, complete=False, warnings=warnings,
            )
        revenue, cogs, package, delivery, ads, other = (
            _decimal(order.selling_price), _decimal(order.product_cost),
            _decimal(order.packaging_cost), _decimal(order.delivery_cost),
            _decimal(order.marketing_cost), _decimal(order.other_expense),
        )
        costs = (cogs, package, delivery, ads, other)
        profit = revenue - sum(costs, Decimal("0")) if revenue is not None and all(x is not None for x in costs) else None
        if profit is None:
            warnings.append("One or more recorded revenue/cost values are missing or invalid.")
        margin = _rounded(profit / revenue * Decimal("100")) if profit is not None and revenue else None
        return OrderProfitability(
            order_id=order.id, status=order.status,
            revenue=_component(revenue, "orders.selling_price"),
            discounts=_component(None, None, "No discount field exists."),
            refunds=_component(None, None, "No refund field exists."),
            cost_of_goods_sold=_component(cogs, "orders.product_cost"),
            packaging_cost=_component(package, "orders.packaging_cost"),
            delivery_cost=_component(delivery, "orders.delivery_cost"),
            advertising_cost=_component(ads, "orders.marketing_cost"),
            other_order_costs=_component(other, "orders.other_expense"),
            net_profit=_component(profit, "recorded selling_price less recorded order costs", "Observed estimate; discounts/refunds are unavailable."),
            profit_margin_percent=margin,
            complete=False, warnings=warnings,
        )

    @staticmethod
    def products(db: Session, business_id: int, start_date=None, end_date=None) -> list[ProductProfitability]:
        rows = (
            db.query(OrderItem, Order)
            .join(Order, (Order.id == OrderItem.order_id) & (Order.business_id == OrderItem.business_id))
            .filter(OrderItem.business_id == business_id, Order.business_id == business_id, Order.status == DELIVERED)
        )
        business_date = func.coalesce(Order.confirmed_order_date, Order.discord_created_at, Order.created_at)
        if start_date:
            rows = rows.filter(business_date >= datetime.combine(start_date, time.min))
        if end_date:
            rows = rows.filter(business_date < datetime.combine(end_date + timedelta(days=1), time.min))
        rows = rows.order_by(OrderItem.id).all()
        grouped = defaultdict(list)
        for item, order in rows:
            key = (item.sku or item.normalized_name or item.product_name or f"item:{item.id}").strip().casefold()
            grouped[key].append((item, order))
        result = []
        for key, values in sorted(grouped.items()):
            revenue = _sum_known([_decimal(item.total_price) for item, _ in values])
            costs = _sum_known([_decimal(item.total_cost) for item, _ in values])
            contribution, margin = DeterministicProfitabilityService.product_contribution(
                revenue, costs, source="item revenue less item cost"
            )
            units = sum(int(item.quantity or 0) for item, _ in values)
            result.append(ProductProfitability(
                product_key=key,
                product_name=next((item.product_name for item, _ in values if item.product_name), None),
                sku=next((item.sku for item, _ in values if item.sku), None),
                units_sold=units,
                revenue=_component(revenue, "order_items.total_price for delivered orders", "Recorded prices; discounts/refunds not represented."),
                cost_of_goods_sold=_component(costs, "order_items.total_cost for delivered orders"),
                contribution_profit=contribution.model_copy(update={"note": "Contribution before order-level packaging, delivery, advertising, and business expenses."}),
                contribution_margin_percent=margin,
                complete=False,
                warnings=["Order-level packaging, delivery, advertising, discounts, and refunds cannot be allocated to products with the current schema."],
            ))
        return result
