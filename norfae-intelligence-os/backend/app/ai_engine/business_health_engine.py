class BusinessHealthEngine:

    # ===================================
    # HEALTH SCORE
    # ===================================

    @staticmethod
    def calculate_health_score(
        profit_margin: float,
        order_volume: int
    ):

        score = 0

        score += min(
            profit_margin,
            50
        )

        score += min(
            order_volume / 10,
            50
        )

        return round(score, 2)