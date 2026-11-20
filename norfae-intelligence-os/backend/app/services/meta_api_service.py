class MetaAPIService:

    # ===================================
    # META API SERVICE STATUS
    # ===================================

    @staticmethod
    def service_status():

        return {

            "service": "meta_ads",

            "initialized": True,

            "connected": None,

            "message": (
                "Meta API integration "
                "not configured yet"
            )
        }