class ForecastingEngine:

    # ===================================
    # REVENUE FORECAST
    # ===================================

    @staticmethod
    def forecast_revenue(
        current_revenue: float,
        growth_rate: float
    ):

        return (
            current_revenue *
            (1 + growth_rate)
        )