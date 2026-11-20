class CreativeAnalysisService:

    # ===================================
    # ANALYZE CREATIVE PERFORMANCE
    # ===================================

    @staticmethod
    def analyze_creative(
        ctr: float,
        roas: float,
        spend: float
    ):

        score = 0

        # CTR Score
        if ctr >= 3:
            score += 35

        elif ctr >= 2:
            score += 20

        # ROAS Score
        if roas >= 4:
            score += 45

        elif roas >= 2:
            score += 25

        # Spend Efficiency
        if spend <= 5000:
            score += 20

        # Final Classification
        if score >= 80:
            status = "winning"

        elif score >= 50:
            status = "stable"

        else:
            status = "weak"

        return {
            "creative_score": score,
            "status": status
        }