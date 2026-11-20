from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from app.models.order_item_model import OrderItem

from app.services.product_normalization_service import ProductNormalizationService
from app.services.deterministic_profitability_service import DeterministicProfitabilityService
from app.schemas.intelligence_schema import (
    ProductIntelligenceItem,
    ProductIntelligencePage,
    ProfitabilityComponent,
)
from sqlalchemy import func
from app.models import Order, Product


def _amount(value):
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
        return parsed if parsed.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _sum_values(values):
    if not values or any(value is None for value in values):
        return None
    return sum(values, Decimal("0"))


def _component(value, source, note=None):
    return ProfitabilityComponent(
        amount=float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if value is not None else None,
        available=value is not None,
        source=source,
        note=note,
    )


class ProductIntelligenceService:

    @staticmethod
    def analyze_business(
        db: Session,
        business_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> ProductIntelligencePage:
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must be on or before end_date.")
        business_date = func.coalesce(Order.confirmed_order_date, Order.discord_created_at, Order.created_at)

        def load_rows(period_start=None, period_end=None):
            query = (
                db.query(OrderItem, Order)
                .join(Order, (Order.id == OrderItem.order_id) & (Order.business_id == OrderItem.business_id))
                .filter(OrderItem.business_id == business_id, Order.business_id == business_id)
            )
            if period_start:
                query = query.filter(business_date >= datetime.combine(period_start, time.min))
            if period_end:
                query = query.filter(business_date < datetime.combine(period_end + timedelta(days=1), time.min))
            return query.order_by(OrderItem.id).all()

        products = db.query(Product).filter(Product.business_id == business_id).order_by(Product.id).all()
        current_rows = load_rows(start_date, end_date)
        previous_start = previous_end = None
        if start_date and end_date:
            days = (end_date - start_date).days + 1
            previous_end = start_date - timedelta(days=1)
            previous_start = previous_end - timedelta(days=days - 1)
            previous_rows = load_rows(previous_start, previous_end)
        else:
            previous_rows = []

        products_by_sku = defaultdict(list)
        for product in products:
            if product.sku and product.sku.strip():
                products_by_sku[product.sku.strip().casefold()].append(product)
        products_by_name = defaultdict(list)
        for product in products:
            if product.name:
                products_by_name[
                    ProductNormalizationService.normalize_product_name(product.name)
                ].append(product)

        def product_for_item(item):
            if item.sku and item.sku.strip():
                found = products_by_sku.get(item.sku.strip().casefold(), [])
                if found:
                    return found[0] if len(found) == 1 else None
            normalized = ProductNormalizationService.normalize_product_name(
                item.product_name or item.normalized_name or ""
            )
            found = products_by_name.get(normalized, [])
            return found[0] if len(found) == 1 else None

        def aggregate(rows):
            stats = defaultdict(lambda: {
                "orders": set(), "delivered_ids": set(), "cancelled_ids": set(),
                "returned_ids": set(), "units": 0, "quantity_missing": False,
                "revenue": [], "costs": [],
            })
            unmatched = 0
            for item, order in rows:
                product = product_for_item(item)
                if product is None:
                    unmatched += 1
                    continue
                metric = stats[product.id]
                metric["orders"].add(order.id)
                status = (order.status or "").upper()
                if status == "DELIVERED":
                    metric["delivered_ids"].add(order.id)
                    try:
                        quantity = int(item.quantity)
                        if quantity <= 0:
                            metric["quantity_missing"] = True
                        else:
                            metric["units"] += quantity
                    except (TypeError, ValueError):
                        metric["quantity_missing"] = True
                    metric["revenue"].append(_amount(item.total_price))
                    metric["costs"].append(_amount(item.total_cost))
                elif status == "CANCELLED":
                    metric["cancelled_ids"].add(order.id)
                elif status == "RETURNED":
                    metric["returned_ids"].add(order.id)
            for product_id, metric in stats.items():
                if metric["delivered_ids"]:
                    metric["revenue_total"] = _sum_values(metric["revenue"])
                    metric["cost_total"] = _sum_values(metric["costs"])
                else:
                    metric["revenue_total"] = Decimal("0")
                    metric["cost_total"] = Decimal("0")
            return stats, unmatched

        current, unmatched_count = aggregate(current_rows)
        previous, previous_unmatched = aggregate(previous_rows)
        if previous_unmatched:
            unmatched_count += previous_unmatched

        items = []
        for product in products:
            metric = current.get(product.id, {
                "orders": set(), "delivered_ids": set(), "cancelled_ids": set(),
                "returned_ids": set(), "units": 0, "quantity_missing": False,
                "revenue_total": Decimal("0"),
                "cost_total": Decimal("0"),
            })
            delivered_count = len(metric["delivered_ids"])
            order_count = len(metric["orders"])
            revenue = metric["revenue_total"]
            product_cost = metric["cost_total"]
            contribution, margin = DeterministicProfitabilityService.product_contribution(
                revenue, product_cost,
                source="delivered order-item revenue less delivered order-item cost",
            )
            average_price = (
                float((revenue / metric["units"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                if revenue is not None and metric["units"] > 0 and not metric["quantity_missing"] else None
            )
            prior = previous.get(product.id)
            change = None
            unusual = False
            if (
                prior and delivered_count >= 3
                and len(prior["delivered_ids"]) >= 3
                and prior["revenue_total"] not in (None, Decimal("0"))
                and revenue is not None
            ):
                change = float(((revenue - prior["revenue_total"]) / prior["revenue_total"] * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                unusual = abs(change) >= 50
            cancellation_count = len(metric["cancelled_ids"])
            return_count = len(metric["returned_ids"])
            cancellation_rate = round(cancellation_count / order_count * 100, 2) if order_count else None
            return_rate = round(return_count / order_count * 100, 2) if order_count else None
            amount = contribution.amount
            if not order_count:
                status = "no_sales"
            elif amount is None:
                status = "incomplete_data"
            elif amount < 0:
                status = "negative_contribution"
            elif order_count >= 5 and ((cancellation_rate or 0) + (return_rate or 0)) >= 30:
                status = "fulfillment_risk"
            elif amount > 0:
                status = "positive_contribution"
            else:
                status = "break_even"
            recommendations = []
            if not order_count:
                recommendations.append("No matching orders are recorded in this period; collect sales history before judging performance.")
            elif amount is None:
                recommendations.append("Complete order-item price and cost records before evaluating product contribution.")
            elif amount < 0:
                recommendations.append("Review the product's recorded selling price and unit costs; delivered item contribution is negative.")
            if order_count >= 5 and ((cancellation_rate or 0) + (return_rate or 0)) >= 30:
                recommendations.append("Review product-specific cancellation and return reasons; the observed rate is at least 30% on five or more orders.")
            if unusual:
                direction = "increased" if change and change > 0 else "decreased"
                recommendations.append(f"Investigate the {direction} in delivered revenue versus the previous equal-length period; the change exceeded 50% with at least three delivered orders in both periods.")
            if not recommendations and amount is not None and amount > 0:
                recommendations.append("Maintain current product data and monitor contribution as more delivered orders accumulate.")
            warnings = ["Contribution excludes order-level delivery, packaging, advertising, and general business expenses; it is not fully allocated business profit."]
            if order_count and (cancellation_count or return_count):
                warnings.append("Return/cancellation counts use order status; refund amounts and recovered costs are unavailable.")
            if metric["quantity_missing"]:
                warnings.append("One or more delivered order-item quantities are missing or invalid; average selling price per unit is unavailable.")
            items.append(ProductIntelligenceItem(
                product_id=product.id, name=product.name, sku=product.sku,
                total_units_sold=metric["units"], order_count=order_count,
                delivered_orders=delivered_count, cancelled_orders=cancellation_count,
                returned_orders=return_count, cancellation_rate_percent=cancellation_rate,
                return_rate_percent=return_rate,
                revenue=_component(revenue, "delivered order_items.total_price"),
                recorded_product_cost=_component(product_cost, "delivered order_items.total_cost"),
                product_contribution=contribution,
                contribution_margin_percent=margin,
                average_selling_price=average_price,
                previous_period_revenue_change_percent=change,
                unusual_performance_change=unusual,
                performance_status=status,
                fully_allocated_business_profit=ProfitabilityComponent(
                    amount=None, available=False,
                    note="Cannot allocate delivery, packaging, advertising, business expenses, discounts, and refunds to this product from the current schema.",
                ),
                recommendations=recommendations, warnings=warnings,
            ))

        ranked = [item for item in items if item.delivered_orders and item.product_contribution.available]
        ranked.sort(key=lambda item: (item.product_contribution.amount, item.revenue.amount or 0), reverse=True)
        best_id = ranked[0].product_id if ranked else None
        lowest_id = ranked[-1].product_id if ranked else None
        items.sort(key=lambda item: (item.product_contribution.amount is not None, item.product_contribution.amount or 0), reverse=True)
        total = len(items)
        offset = (page - 1) * page_size
        warnings = []
        if unmatched_count:
            warnings.append(f"{unmatched_count} order-item records were unmatched or ambiguously matched and were excluded from catalog-level metrics.")
        duplicate_skus = sum(len(group) > 1 for group in products_by_sku.values())
        duplicate_names = sum(len(group) > 1 for group in products_by_name.values())
        if duplicate_skus or duplicate_names:
            warnings.append(f"Ambiguous catalog identifiers detected: duplicate normalized SKUs={duplicate_skus}, duplicate normalized names={duplicate_names}; matched order items were not assigned arbitrarily.")
        if not products:
            warnings.append("No catalog products are registered for this business.")
        return ProductIntelligencePage(
            business_id=business_id, start_date=start_date, end_date=end_date,
            total_products=total, page=page, page_size=page_size,
            best_performing_product_id=best_id, lowest_performing_product_id=lowest_id,
            products=items[offset:offset + page_size], warnings=warnings,
        )

    @staticmethod
    def get_product(db: Session, business_id: int, product_id: int, start_date=None, end_date=None):
        product = db.query(Product).filter(
            Product.business_id == business_id, Product.id == product_id
        ).first()
        if product is None:
            return None
        return next(
            (item for item in ProductIntelligenceService.analyze_business(
                db, business_id, start_date, end_date, page=1, page_size=100000
            ).products if item.product_id == product_id),
            None,
        )

    @staticmethod
    def get_product_intelligence(db: Session):

        # ===================================
        # LOAD ORDER ITEMS
        # ===================================

        order_items = db.query(OrderItem).options(joinedload(OrderItem.order)).all()


        # ===================================
        # PRODUCT STORAGE
        # ===================================

        products = defaultdict(
            lambda: {
                "product_name": "",
                "normalized_name": "",
                "sku": "",
                "size": "standard",
                "orders": 0,
                "delivered": 0,
                "cancelled": 0,
                "returned": 0,
                "revenue": 0,
                "profit": 0,
                "success_rate": 0,
                "profit_margin": 0,
                "loss_rate": 0,
                "delivery_rate": 0,
                "revenue_per_order": 0,
                "profit_per_order": 0,
                "performance_status": "weak",
                "sample_orders": [],
                "sample_order_ids": [],
                "sample_order_item_ids": [],
                "verified": False,
            }
        )

        # ===================================
        # PROCESS ITEMS
        # ===================================

        for item in order_items:

            # ===============================
            # PRODUCT NAME
            # ===============================

            product_name = item.product_name or "Unknown Product"

            # ===============================
            # NORMALIZED NAME
            # ===============================

            normalized_name = ProductNormalizationService.normalize_product_name(
                product_name
            )

            # ===============================
            # SIZE
            # ===============================

            product_size = item.size or item.variant or "standard"

            product_size = str(product_size).lower().strip()

            # ===============================
            # SKU
            # ===============================

            sku = ""

            if item.sku:

                sku = str(item.sku).strip().upper()

            # ===============================
            # INVALID SKU FILTER
            # ===============================

            invalid_skus = [
                "",
                "UNKNOWN",
                "UNMATCHED",
                "NONE",
                "NULL",
            ]

            if sku.upper() in invalid_skus:

                sku = ""

            # ===============================
            # GROUP KEY
            # ===============================

            if sku:

                group_key = sku

            else:

                group_key = f"{normalized_name}_" f"{product_size}"

            # ===============================
            # STORE IDENTITY
            # ===============================

            if not products[group_key]["product_name"]:

                products[group_key]["product_name"] = product_name

            products[group_key]["normalized_name"] = normalized_name

            products[group_key]["sku"] = (
                sku if sku else f"{normalized_name}_{product_size}"
            )

            products[group_key]["size"] = product_size

            # ===============================
            # VERIFIED CHECK
            # ===============================

            verified = False

            if sku:

                sku_text = str(sku).strip()

                # REAL SHOPIFY SKU
                # usually numeric like 44115.0

                if sku_text.replace(".", "").isdigit():

                    verified = True

            products[group_key]["verified"] = verified

            # ===============================
            # REVIEW VALIDATION
            # ===============================

            needs_review = True

            sku_text = str(sku or "").strip()
            # SHOULD BE VERIFIED

            if sku_text.replace(".", "").isdigit():

                needs_review = False

            products[group_key]["needs_review"] = needs_review

            # ===============================
            # SAMPLE ORDERS
            # ===============================

            already_exists = False

            for existing_sample in products[group_key]["sample_orders"]:

                if existing_sample["order_item_id"] == item.id:

                    already_exists = True

                    break

            if not already_exists:

                if len(products[group_key]["sample_orders"]) < 5:

                    products[group_key]["sample_orders"].append(
                        {
                            "order_id": (
                                item.order.internal_order_id
                                if item.order
                                else item.order_id
                            ),
                            "order_item_id": item.id,
                            "product_name": item.product_name,
                            "sku": item.sku or "",
                            "size": (item.size or "standard"),
                        }
                    )

            # ===============================
            # SAMPLE ORDER IDS
            # ===============================

            if item.order:

                internal_order_id = item.order.internal_order_id

                if internal_order_id:

                    if internal_order_id not in products[group_key]["sample_order_ids"]:

                        if len(products[group_key]["sample_order_ids"]) < 5:

                            products[group_key]["sample_order_ids"].append(
                                internal_order_id
                            )

            # ===============================
            # SAMPLE ORDER ITEM IDS
            # ===============================

            if item.id:

                if item.id not in products[group_key]["sample_order_item_ids"]:

                    if len(products[group_key]["sample_order_item_ids"]) < 5:

                        products[group_key]["sample_order_item_ids"].append(item.id)

            # ===============================
            # QUANTITY
            # ===============================

            quantity = int(item.quantity or 1)

            products[group_key]["orders"] += quantity

            # ===============================
            # STATUS
            # ===============================

            order_status = ""

            if item.order:

                order_status = (item.order.status or "").upper()

            # ===============================
            # DELIVERED
            # ===============================

            if order_status == "DELIVERED":

                products[group_key]["delivered"] += quantity

                revenue = float(item.total_price or 0)

                profit = float(item.profit or 0)

                if revenue < 0:

                    revenue = 0

                products[group_key]["revenue"] += revenue

                products[group_key]["profit"] += profit

            # ===============================
            # CANCELLED
            # ===============================

            elif order_status == "CANCELLED":

                products[group_key]["cancelled"] += quantity

            # ===============================
            # RETURNED
            # ===============================

            elif order_status == "RETURNED":

                products[group_key]["returned"] += quantity

        # ===================================
        # KPI CALCULATIONS
        # ===================================

        for product in products.values():

            orders = float(product["orders"] or 0)

            delivered = float(product["delivered"] or 0)

            cancelled = float(product["cancelled"] or 0)

            returned = float(product["returned"] or 0)

            revenue = float(product["revenue"] or 0)

            profit = float(product["profit"] or 0)

            # ===============================
            # SUCCESS RATE
            # ===============================

            if orders > 0:

                product["success_rate"] = round((delivered / orders) * 100, 2)

            else:

                product["success_rate"] = 0

            # ===============================
            # LOSS RATE
            # ===============================

            if orders > 0:

                product["loss_rate"] = round(((cancelled + returned) / orders) * 100, 2)

            else:

                product["loss_rate"] = 0

            # ===============================
            # DELIVERY RATE
            # ===============================

            product["delivery_rate"] = product["success_rate"]

            # ===============================
            # PROFIT MARGIN
            # ===============================

            if revenue > 0:

                product["profit_margin"] = round((profit / revenue) * 100, 2)

            else:

                product["profit_margin"] = 0

            # ===============================
            # REVENUE PER ORDER
            # ===============================

            if delivered > 0:

                product["revenue_per_order"] = round(revenue / delivered, 2)

            else:

                product["revenue_per_order"] = 0

            # ===============================
            # PROFIT PER ORDER
            # ===============================

            if delivered > 0:

                product["profit_per_order"] = round(profit / delivered, 2)

            else:

                product["profit_per_order"] = 0

            # ===============================
            # PERFORMANCE STATUS
            # ===============================

            if orders < 3:

                product["performance_status"] = "testing"

            elif profit <= 0:

                product["performance_status"] = "loss"

            elif product["loss_rate"] >= 35:

                product["performance_status"] = "risky"

            elif (
                product["profit_margin"] >= 35
                and product["success_rate"] >= 80
                and delivered >= 5
            ):

                product["performance_status"] = "elite"

            elif product["profit_margin"] >= 20 and product["success_rate"] >= 60:

                product["performance_status"] = "strong"

            else:

                product["performance_status"] = "weak"

            # ===============================
            # FINAL ROUNDING
            # ===============================

            product["revenue"] = round(revenue, 2)

            product["profit"] = round(profit, 2)

        # ===================================
        # FINAL SORTING
        # ===================================

        sorted_products = sorted(
            products.values(),
            key=lambda x: (x["profit"], x["revenue"], x["delivered"]),
            reverse=True,
        )

        return sorted_products
