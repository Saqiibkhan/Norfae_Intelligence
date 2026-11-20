from apscheduler.schedulers.background import (
    BackgroundScheduler,
)

from app.core.database import SessionLocal
from app.core.tenant_context import tenant_scope
from app.models.business_model import Business

from app.services.meta_expense_service import (
    MetaExpenseService,
)

scheduler = BackgroundScheduler()


def sync_meta_expenses_job(business_id: int):

    with tenant_scope(business_id):
        db = SessionLocal()

        try:

            MetaExpenseService.sync_yesterday_spend(db)

        finally:

            db.close()


def start_scheduler(business_ids: list[int]):
    if not business_ids or any(not isinstance(item, int) or item <= 0 for item in business_ids):
        raise ValueError("Explicit valid business IDs are required to start the scheduler.")

    requested = sorted(set(business_ids))
    with SessionLocal() as db:
        active = {
            row.id
            for row in db.query(Business)
            .filter(Business.id.in_(requested), Business.is_active.is_(True))
            .all()
        }
    if active != set(requested):
        raise ValueError("Every scheduled business must exist and be active.")

    for business_id in requested:
        scheduler.add_job(
            sync_meta_expenses_job,
            "cron",
            hour=0,
            minute=5,
            timezone="Asia/Karachi",
            args=[business_id],
            id=f"meta-expenses-{business_id}",
            replace_existing=True,
        )

    scheduler.start()
