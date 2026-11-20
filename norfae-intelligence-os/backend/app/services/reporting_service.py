from datetime import datetime

from datetime import timedelta

from app.core.timezone import pakistan_now

from sqlalchemy.orm import Session

from app.services.analytics_service import AnalyticsService

from app.models.expense_model import Expense

from app.models.order_model import Order

from app.models.meta_daily_stats_model import MetaDailyStats

from app.ai_engine.forecasting_engine import ForecastingEngine

from app.utils.report_formatters import ReportFormatter


class ReportingService:

    # ===================================
    # GENERATE BUSINESS REPORT
    # ===================================

    @staticmethod
    def generate_report(db: Session, report_type: str, start_date=None, end_date=None):

        # ===================================
        # CORE ANALYTICS
        # ===================================

        analytics = AnalyticsService.get_order_analytics(
            db=db, start_date=start_date, end_date=end_date
        )

        true_business_profit = analytics["true_business_profit"]

        true_profit_margin = analytics["true_net_margin"]

        # ===================================
        # FORECASTING
        # ===================================

        forecasted_revenue = ForecastingEngine.forecast_revenue(
            analytics["net_revenue"], 0.10
        )

        # ===================================
        # REPORT PERIOD
        # ===================================

        formatted_start = start_date.strftime("%d %b %Y") if start_date else "All Time"

        formatted_end = end_date.strftime("%d %b %Y") if end_date else "Present"

        # ===================================
        # META ADS ANALYTICS
        # ===================================

        meta_query = db.query(MetaDailyStats)

        if start_date and end_date:

            meta_query = meta_query.filter(
                MetaDailyStats.stats_date >= start_date.date(),
                MetaDailyStats.stats_date < end_date.date(),
            )

        meta_stats = meta_query.all()
        print("REPORT START:", start_date)
        print("REPORT END:", end_date)

        for row in meta_stats:
            print(
                row.stats_date,
                row.spend,
            )

        meta_spend = sum(x.spend for x in meta_stats)

        meta_revenue = sum(x.gross_revenue for x in meta_stats)

        meta_profit = sum(x.net_profit for x in meta_stats)

        meta_orders = sum(x.total_orders for x in meta_stats)

        meta_messages = sum(x.instagram_messages for x in meta_stats)

        meta_roas = (
            round(
                meta_revenue / meta_spend,
                2,
            )
            if meta_spend > 0
            else 0
        )
        # ===================================
        # CITY ANALYTICS
        # ===================================

        orders_query = db.query(Order)

        if start_date and end_date:

            orders_query = orders_query.filter(
                Order.discord_created_at >= start_date,
                Order.discord_created_at <= end_date,
            )

        orders = orders_query.all()

        city_stats = {}

        for order in orders:

            city = order.city.strip().title() if order.city else "Unknown"

            if city not in city_stats:

                city_stats[city] = 0

            city_stats[city] += 1

        top_cities = sorted(
            city_stats.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        # ===================================
        # RESPONSE
        # ===================================

        return {
            "report_type": report_type,
            "generated_at": pakistan_now(),
            "report_period": {
                "start_date": formatted_start,
                "end_date": formatted_end,
            },
            "meta_ads": {
                "ad_spend": round(meta_spend, 2),
                "orders": meta_orders,
                "messages": meta_messages,
            },
            "top_cities": top_cities,
            "summary": {
                # ==========================
                # ORDERS
                # ==========================
                "total_orders": analytics["total_orders"],
                "delivered_orders": analytics["delivered_orders"],
                "cancelled_orders": analytics["cancelled_orders"],
                "returned_orders": analytics["returned_orders"],
                "pending_orders": analytics["pending_orders"],
                # ==========================
                # REVENUE
                # ==========================
                "gross_revenue": analytics["gross_revenue"],
                "net_revenue": analytics["net_revenue"],
                # ==========================
                # COSTS
                # ==========================
                "order_costs": analytics["order_costs"],
                "delivery_cost": analytics["delivery_cost"],
                "return_loss": analytics["return_loss"],
                "product_cost": analytics["product_cost"],
                "packaging_cost": analytics["packaging_cost"],
                "marketing_cost": analytics["marketing_cost"],
                "total_cost": analytics["total_cost"],
                "business_expenses": analytics["business_expenses"],
                "operating_expenses": analytics["operating_expenses"],
                "external_expenses": analytics["operating_expenses"],
                # ==========================
                # PROFITABILITY
                # ==========================
                "gross_profit": analytics["gross_profit"],
                "net_profit": analytics["net_profit"],
                "true_business_profit": round(true_business_profit, 2),
                "true_profit_margin": round(true_profit_margin, 2),
                # ==========================
                # KPIs
                # ==========================
                "average_order_value": analytics["average_order_value"],
                "delivery_success_rate": analytics["delivery_success_rate"],
                "cancellation_rate": analytics["cancellation_rate"],
                "return_rate": analytics["return_rate"],
                # ==========================
                # FORECAST
                # ==========================
                "forecasted_revenue": round(forecasted_revenue, 2),
            },
        }
