from fastapi.responses import JSONResponse


class ErrorHandler:

    # ===================================
    # GENERIC ERROR RESPONSE
    # ===================================

    @staticmethod
    def server_error(
        message: str
    ):

        return JSONResponse(

            status_code=500,

            content={

                "success": False,

                "error": message
            }
        )

    # ===================================
    # NOT FOUND
    # ===================================

    @staticmethod
    def not_found(
        message: str
    ):

        return JSONResponse(

            status_code=404,

            content={

                "success": False,

                "error": message
            }
        )