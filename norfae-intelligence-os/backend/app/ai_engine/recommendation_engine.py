class RecommendationEngine:

    # ===================================
    # BUSINESS RECOMMENDATIONS
    # ===================================

    @staticmethod
    def generate_recommendations(
        profit_margin: float,
        business_health_score: float
    ):

        recommendations = []

        if profit_margin < 20:

            recommendations.append(
                "Reduce operational costs"
            )

        if business_health_score < 50:

            recommendations.append(
                "Improve marketing efficiency"
            )

        if not recommendations:

            recommendations.append(
                "Business operating efficiently"
            )

        return recommendations