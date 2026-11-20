class ProductAnalysisService:

    # ===================================
    # PRODUCT VIABILITY ANALYSIS
    # ===================================

    @staticmethod
    def analyze_product(
        profit_margin: float,
        demand_score: float,
        competition_score: float
    ):

        viability_score = (
            profit_margin * 0.4
            +
            demand_score * 0.4
            +
            competition_score * 0.2
        )

        if viability_score >= 80:
            status = "high_potential"

        elif viability_score >= 60:
            status = "moderate"

        else:
            status = "low_potential"

        return {
            "viability_score": round(
                viability_score,
                2
            ),
            "status": status
        }