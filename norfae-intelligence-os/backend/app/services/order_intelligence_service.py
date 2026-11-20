from app.models.order_model import Order

from app.services.profit_calculator_service import ProfitCalculatorService


class OrderIntelligenceService:

    # ===================================
    # TOTAL COST
    # ===================================

    @staticmethod
    def calculate_total_cost(order: Order):

        status = order.status.upper() if order.status else ""

        # ===================================
        # CANCELLED
        # ===================================

        if status == "CANCELLED":

            return round((order.packaging_cost or 0) + (order.other_expense or 0), 2)

        # ===================================
        # RETURNED
        # ===================================

        if status == "RETURNED":

            return round(
                (order.delivery_cost or 0) * 2
                + (order.packaging_cost or 0)
                + (order.other_expense or 0),
                2,
            )

        # ===================================
        # NORMAL ORDERS
        # ===================================

        return ProfitCalculatorService.calculate_total_cost(order)

    # ===================================
    # NET PROFIT
    # ===================================

    @staticmethod
    def calculate_net_profit(order: Order):

        status = order.status.upper() if order.status else ""

        # ===================================
        # CANCELLED / RETURNED
        # ===================================

        if status in ["CANCELLED", "RETURNED"]:

            return round(-(OrderIntelligenceService.calculate_total_cost(order)), 2)

        # ===================================
        # NORMAL
        # ===================================

        return ProfitCalculatorService.calculate_net_profit(order)

    # ===================================
    # PROFIT MARGIN
    # ===================================

    @staticmethod
    def calculate_profit_margin(order: Order):

        status = order.status.upper() if order.status else ""

        # ===================================
        # NEGATIVE ORDERS
        # ===================================

        if status in ["CANCELLED", "RETURNED"]:

            return 0

        return ProfitCalculatorService.calculate_margin(order)
