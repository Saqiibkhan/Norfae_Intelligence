import asyncio
import logging

from app.core.database import SessionLocal
from app.core.tenant_context import tenant_scope
from app.models.business_model import Business
from app.services.meta_sync_service import MetaSyncService


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
                result = MetaSyncService.sync_today_stats(db)
                if not isinstance(result, dict) or result.get("success") is not True:
                    message = result.get("message") if isinstance(result, dict) else None
                    code = (
                        "configuration_missing"
                        if message in {"Settings not found", "Meta credentials missing"}
                        else "sync_failed"
                    )
                    return {"success": False, "error_code": code}
                return {"success": True}
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
