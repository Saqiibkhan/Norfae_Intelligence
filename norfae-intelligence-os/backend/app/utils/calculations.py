class Calculations:

    # ===================================
    # PROFIT CALCULATION
    # ===================================

    @staticmethod
    def calculate_profit(
        revenue: float,
        expenses: float
    ):

        return revenue - expenses

    # ===================================
    # PROFIT MARGIN
    # ===================================

    @staticmethod
    def calculate_profit_margin(
        profit: float,
        revenue: float
    ):

        if revenue <= 0:

            return 0

        return (
            profit / revenue
        ) * 100