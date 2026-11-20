class OrderAnalysisService:

    # ===================================
    # ANALYZE ORDER STATUS
    # ===================================

    @staticmethod
    def analyze_order_status(status: str):

        status = status.lower()

        if status == "delivered":

            return {
                "health_score": 100,
                "category": "successful"
            }

        elif status == "cancelled":

            return {
                "health_score": 20,
                "category": "high_risk"
            }

        elif status == "returned":

            return {
                "health_score": 40,
                "category": "problematic"
            }

        return {
            "health_score": 60,
            "category": "processing"
        }