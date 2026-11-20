from fastapi import APIRouter, Query

from sqlalchemy.orm import Session

from app.core.database import SessionLocal

from app.models.order_model import Order

from app.models.expense_model import Expense

from app.models.product_model import Product

from datetime import datetime

from sqlalchemy import func

from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# ===================================
# DASHBOARD OVERVIEW
# ===================================


@router.get("/overview")
def dashboard_overview(start_date: str = Query(None), end_date: str = Query(None)):

    db: Session = SessionLocal()

    # ===================================
    # FETCH DATA
    # ===================================

    orders_query = db.query(Order)

    expenses_query = db.query(Expense)

    all_orders = db.query(Order).all()

    # ===================================
    # DATE FILTERING
    # ===================================

    start = None
    end = None

    if start_date and end_date:

        start = datetime.strptime(start_date, "%Y-%m-%d")

        end = datetime.strptime(end_date, "%Y-%m-%d")

        orders_query = orders_query.filter(
            Order.discord_created_at >= start, Order.discord_created_at <= end
        )

        expenses_query = expenses_query.filter(
            func.date(Expense.created_at) >= start.date(),
            func.date(Expense.created_at) <= end.date(),
        )

    orders = orders_query.all()

    expenses = expenses_query.all()

    products = db.query(Product).all()

    analytics = AnalyticsService.get_order_analytics(
        db=db,
        start_date=start,
        end_date=end,
    )

    # ===================================
    # ORDER ANALYTICS
    # ===================================

    total_orders = len(orders)

    delivered_orders = len([order for order in orders if order.status == "DELIVERED"])

    cancelled_orders = len([order for order in orders if order.status == "CANCELLED"])

    returned_orders = len([order for order in orders if order.status == "RETURNED"])

    pending_orders = len(
        [
            order
            for order in all_orders
            if order.status in ["PENDING", "CONFIRMATION_PENDING"]
        ]
    )

    active_orders = len([order for order in all_orders if order.status == "PROCESSING"])

    # ===================================
    # PRODUCT ANALYTICS
    # ===================================

    total_products = len(products)

    low_stock_products = len([product for product in products if product.stock <= 5])

    # ===================================
    # HEALTH SCORE
    # ===================================

    health_score = 100

    if cancelled_orders > 0:

        cancellation_rate = (
            (cancelled_orders / total_orders) * 100 if total_orders > 0 else 0
        )

        health_score -= cancellation_rate

    if returned_orders > 0:

        return_rate = (returned_orders / total_orders) * 100 if total_orders > 0 else 0

        health_score -= return_rate

    if analytics["true_business_profit"] < 0:

        health_score -= 20

    health_score = max(0, round(health_score, 2))

    db.close()

    # ===================================
    # RESPONSE
    # ===================================

    return {
        # ===============================
        # ORDERS
        # ===============================
        "total_orders": total_orders,
        "delivered_orders": delivered_orders,
        "cancelled_orders": cancelled_orders,
        "returned_orders": returned_orders,
        "pending_orders": pending_orders,
        "active_orders": active_orders,
        # ===============================
        # FINANCIALS
        # ===============================
        "revenue": analytics["gross_revenue"],
        "gross_profit": analytics["gross_profit"],
        "return_loss": analytics["return_loss"],
        "profit": analytics["net_profit"],
        "expenses": analytics["business_expenses"],
        "marketing_cost": analytics["marketing_cost"],
        "operating_expenses": analytics["operating_expenses"],
        "true_business_profit": analytics["true_business_profit"],
        "profit_margin": analytics["true_net_margin"],
        "delivery_costs": analytics["delivery_cost"],
        "product_cost": analytics["product_cost"],
        "packaging_cost": analytics["packaging_cost"],
        # ===============================
        # PRODUCTS
        # ===============================
        "total_products": total_products,
        "low_stock_products": low_stock_products,
        # ===============================
        # HEALTH
        # ===============================
        "health_score": health_score,
    }
