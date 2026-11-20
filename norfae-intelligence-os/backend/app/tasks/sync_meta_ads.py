import asyncio
import logging

from app.core.database import SessionLocal
from app.core.tenant_context import tenant_scope
from app.models.business_model import Business
from app.core.timezone import pakistan_now
from app.services.meta_insights_sync_service import MetaInsightsSyncService


logger = logging.getLogger(__name__)


class MetaAdsSyncTask:
    @staticmethod
    def sync_once(business_id: int) -> dict[str, object]:
        if isinstance(business_id, bool) or not isinstance(business_id, int) or business_id <= 0:
            raise ValueError("A valid business ID is required for Meta sync.")

        with tenant_scope(business_id):
            check_db = SessionLocal()
            try:
                business = check_db.query(Business).filter(
                    Business.id == business_id, Business.is_active.is_(True)
                ).first()
                if business is None:
                    return {"success": False, "error_code": "business_unavailable"}
            finally:
                check_db.close()

            db = SessionLocal()
            try:
                today = pakistan_now().date()
                result = MetaInsightsSyncService.sync(db, business_id, None, today, today)
                if result["status"] == "completed":
                    return {"success": True}
                return {"success": False, "error_code": result["run"].get("error_category", "sync_failed")}
            except Exception as error:
                logger.warning(
                    "Meta scheduled sync failed",
                    extra={"business_id": business_id, "error_type": type(error).__name__},
                )
                return {"success": False, "error_code": "sync_failed"}
            finally:
                db.close()

    @staticmethod
    async def run(business_id: int):
        if isinstance(business_id, bool) or not isinstance(business_id, int) or business_id <= 0:
            raise ValueError("A valid business ID is required for Meta sync.")

        while True:
            result = MetaAdsSyncTask.sync_once(business_id)
            logger.info(
                "Meta scheduled sync completed",
                extra={"business_id": business_id, "success": result["success"],
                       "error_code": result.get("error_code")},
            )
            await asyncio.sleep(300)
