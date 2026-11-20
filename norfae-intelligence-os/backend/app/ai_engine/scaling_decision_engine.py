class ScalingDecisionEngine:

    # ===================================
    # SCALING DECISION
    # ===================================

    @staticmethod
    def should_scale(
        roas: float,
        profit_margin: float
    ):

        return (
            roas >= 2.5 and
            profit_margin >= 25
        )