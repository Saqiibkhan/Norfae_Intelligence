import asyncio
from datetime import datetime
from app.core.tenant_context import tenant_scope


class DailyReportTask:

    # ===================================
    # GENERATE DAILY REPORTS
    # ===================================

    @staticmethod
    async def run(business_id: int):
        if isinstance(business_id, bool) or business_id <= 0:
            raise ValueError("A valid business ID is required for this task.")

        while True:
            with tenant_scope(business_id):

                print(

                    f"[{datetime.utcnow()}] Business {business_id}: "
                    "Generating daily reports..."
                )

            await asyncio.sleep(86400)
