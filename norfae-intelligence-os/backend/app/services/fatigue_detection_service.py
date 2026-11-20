class FatigueDetectionService:

    # ===================================
    # DETECT CREATIVE FATIGUE
    # ===================================

    @staticmethod
    def detect_fatigue(
        ctr_drop_percentage: float,
        roas_drop_percentage: float
    ):

        if (
            ctr_drop_percentage >= 30
            or
            roas_drop_percentage >= 30
        ):

            return {
                "fatigue_detected": True,
                "severity": "high"
            }

        if (
            ctr_drop_percentage >= 15
            or
            roas_drop_percentage >= 15
        ):

            return {
                "fatigue_detected": True,
                "severity": "medium"
            }

        return {
            "fatigue_detected": False,
            "severity": "low"
        }