from app.models.order_model import Order


class ProfitCalculatorService:

    # ===================================
    # TOTAL COST
    # ===================================

    @staticmethod
    def calculate_total_cost(order: Order):

        return round(
            float(order.product_cost or 0)
            + float(order.delivery_cost or 0)
            + float(order.packaging_cost or 0)
            + float(order.other_expense or 0),
            2,
        )

    # ===================================
    # NET PROFIT
    # ===================================

    @staticmethod
    def calculate_net_profit(order: Order):

        revenue = float(order.selling_price or 0)

        total_cost = ProfitCalculatorService.calculate_total_cost(order)

        return round(revenue - total_cost, 2)

    # ===================================
    # PROFIT MARGIN
    # ===================================

    @staticmethod
    def calculate_margin(order: Order):

        revenue = float(order.selling_price or 0)

        if revenue <= 0:

            return 0

        net_profit = ProfitCalculatorService.calculate_net_profit(order)

        return round((net_profit / revenue) * 100, 2)
