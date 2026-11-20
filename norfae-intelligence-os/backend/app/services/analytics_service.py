from collections import defaultdict

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.order_model import Order

from app.models.expense_model import Expense


class AnalyticsService:

    # ===================================
    # ORDER ANALYTICS
    # ===================================

    @staticmethod
    def get_order_analytics(db: Session, start_date, end_date):

        # ===================================
        # BASE QUERY
        # ===================================

        query = db.query(Order)

        # ===================================
        # DATE FILTER
        # ===================================

        if start_date and end_date:

            query = query.filter(
                and_(
                    Order.discord_created_at >= start_date,
                    Order.discord_created_at <= end_date,
                )
            )

        orders = query.all()

        # ===================================
        # REMOVE INVALID ORDERS
        # ===================================

        orders = [order for order in orders if order.discord_created_at]

        # ===================================
        # ORDER STATES
        # ===================================

        total_orders = len(orders)

        delivered_orders = [order for order in orders if order.status == "DELIVERED"]

        cancelled_orders = [order for order in orders if order.status == "CANCELLED"]

        returned_orders = [order for order in orders if order.status == "RETURNED"]

        pending_orders = [
            order
            for order in orders
            if order.status in ["PENDING", "CONFIRMATION_PENDING"]
        ]

        active_orders = [order for order in orders if order.status == "PROCESSING"]

        # ===================================
        # REVENUE
        # ===================================

        gross_revenue = sum(
            float(order.selling_price or 0) for order in delivered_orders
        )

        net_revenue = gross_revenue

        # ===================================
        # COSTS
        # ===================================

        delivery_cost = sum(
            float(order.delivery_cost or 0) for order in delivered_orders
        )

        product_cost = sum(float(order.product_cost or 0) for order in delivered_orders)

        packaging_cost = sum(
            float(order.packaging_cost or 0) for order in delivered_orders
        )

        expense_query = db.query(Expense)

        if start_date and end_date:

            expense_query = expense_query.filter(
                Expense.expense_date >= start_date,
                Expense.expense_date <= end_date,
            )

        expenses = expense_query.all()

        marketing_cost = sum(
            float(expense.amount or 0)
            for expense in expenses
            if (expense.category and expense.category.lower() == "marketing")
        )

        operating_expenses = sum(
            float(expense.amount or 0)
            for expense in expenses
            if (not expense.category or expense.category.lower() != "marketing")
        )

        other_expense = sum(
            float(order.other_expense or 0) for order in delivered_orders
        )

        order_costs = delivery_cost + product_cost + packaging_cost + other_expense

        business_expenses = marketing_cost + operating_expenses

        total_cost = order_costs

        # ===================================
        # PROFITABILITY
        # ===================================

        gross_profit = (
            gross_revenue
            - product_cost
            - delivery_cost
            - packaging_cost
            - other_expense
        )

        return_loss = 0

        for order in returned_orders:

            return_loss += (
                float(order.delivery_cost or 0)
                + float(order.delivery_cost or 0)
                + float(order.packaging_cost or 0)
            )

        net_profit = gross_profit - return_loss

        true_business_profit = net_profit - marketing_cost - operating_expenses

        # ===================================
        # KPI ENGINE
        # ===================================

        average_order_value = (
            net_revenue / len(delivered_orders) if delivered_orders else 0
        )

        delivery_success_rate = (
            (len(delivered_orders) / total_orders) * 100 if total_orders else 0
        )

        cancellation_rate = (
            (len(cancelled_orders) / total_orders) * 100 if total_orders else 0
        )

        return_rate = (len(returned_orders) / total_orders) * 100 if total_orders else 0

        # ===================================
        # RESPONSE
        # ===================================

        return {
            "total_orders": total_orders,
            "delivered_orders": len(delivered_orders),
            "cancelled_orders": len(cancelled_orders),
            "returned_orders": len(returned_orders),
            "pending_orders": len(pending_orders),
            "active_orders": len(active_orders),
            "gross_revenue": round(gross_revenue, 2),
            "net_revenue": round(net_revenue, 2),
            "delivery_cost": round(delivery_cost, 2),
            "product_cost": round(product_cost, 2),
            "packaging_cost": round(packaging_cost, 2),
            "marketing_cost": round(marketing_cost, 2),
            "other_expense": round(other_expense, 2),
            "total_cost": round(total_cost, 2),
            "gross_profit": round(gross_profit, 2),
            "net_profit": round(net_profit, 2),
            "true_net_margin": (
                round(
                    (true_business_profit / net_revenue) * 100,
                    2,
                )
                if net_revenue
                else 0
            ),
            "average_order_value": round(average_order_value, 2),
            "delivery_success_rate": round(delivery_success_rate, 2),
            "cancellation_rate": round(cancellation_rate, 2),
            "return_rate": round(return_rate, 2),
            "order_costs": round(order_costs, 2),
            "business_expenses": round(
                business_expenses,
                2,
            ),
            "return_loss": round(
                return_loss,
                2,
            ),
            "operating_expenses": round(
                operating_expenses,
                2,
            ),
            "true_business_profit": round(
                true_business_profit,
                2,
            ),
        }

    # ===================================
    # TREND ANALYTICS
    # ===================================

    @staticmethod
    def get_order_trends(db: Session, start_date, end_date):

        # ===================================
        # BASE QUERY
        # ===================================

        query = db.query(Order)

        # ===================================
        # DATE FILTER
        # ===================================

        if start_date and end_date:

            query = query.filter(
                and_(
                    Order.discord_created_at >= start_date,
                    Order.discord_created_at <= end_date,
                )
            )

        orders = query.all()

        # ===================================
        # REMOVE INVALID ORDERS
        # ===================================

        orders = [order for order in orders if order.discord_created_at]

        # ===================================
        # TRENDS
        # ===================================

        trends = defaultdict(
            lambda: {
                "date": "",
                "orders": 0,
                "revenue": 0,
                "profit": 0,
                "delivered": 0,
            }
        )

        for order in orders:

            if not order.discord_created_at:

                continue

            day = order.discord_created_at.strftime("%Y-%m-%d")

            trends[day]["date"] = day

            trends[day]["orders"] += 1

            if order.status == "DELIVERED":

                trends[day]["revenue"] += float(order.selling_price or 0)

                trends[day]["profit"] += float(order.net_profit or 0)

                trends[day]["delivered"] += 1

        return sorted(trends.values(), key=lambda x: x["date"])

    # ===================================
    # CHANGE %
    # ===================================

    @staticmethod
    def calculate_change_percentage(current, previous):

        if previous == 0:

            if current > 0:

                return 100

            return 0

        return round(((current - previous) / previous) * 100, 2)

    # ===================================
    # COMPARATIVE ANALYTICS
    # ===================================

    @staticmethod
    def get_comparative_analytics(
        db, current_start, current_end, previous_start, previous_end
    ):

        # ===================================
        # ALL TIME MODE
        # ===================================

        if not current_start or not current_end:

            return {}

        # ===================================
        # CURRENT PERIOD
        # ===================================

        current = AnalyticsService.get_order_analytics(db, current_start, current_end)

        # ===================================
        # PREVIOUS PERIOD
        # ===================================

        previous = AnalyticsService.get_order_analytics(
            db, previous_start, previous_end
        )

        comparison = {}

        metrics = [
            "total_orders",
            "delivered_orders",
            "cancelled_orders",
            "returned_orders",
            "net_revenue",
            "net_profit",
            "average_order_value",
            "delivery_success_rate",
        ]

        for metric in metrics:

            current_value = current.get(metric, 0)

            previous_value = previous.get(metric, 0)

            comparison[metric] = {
                "current": current_value,
                "previous": previous_value,
                "change_percentage": (
                    AnalyticsService.calculate_change_percentage(
                        current_value, previous_value
                    )
                ),
            }

        return comparison
