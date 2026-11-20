from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.expense_model import Expense
from app.models.meta_daily_stats_model import MetaDailyStats

from app.core.timezone import pakistan_now


class MetaExpenseService:

    @staticmethod
    def sync_yesterday_spend(
        db: Session,
    ):

        yesterday = (pakistan_now() - timedelta(days=1)).date()

        reference = f"meta_{yesterday}"

        existing_expense = (
            db.query(Expense).filter(Expense.external_reference == reference).first()
        )

        if existing_expense:

            return {
                "success": True,
                "message": "Already synced",
            }

        stats = (
            db.query(MetaDailyStats)
            .filter(MetaDailyStats.stats_date == yesterday)
            .first()
        )

        if not stats:

            return {
                "success": False,
                "message": "Meta stats not found",
            }

        expense = Expense(
            title="Meta Ads Spend",
            amount=stats.spend,
            category="marketing",
            source="meta",
            external_reference=reference,
            expense_date=stats.stats_date,
            created_at=pakistan_now(),
        )

        db.add(expense)

        db.commit()

        return {
            "success": True,
            "amount": stats.spend,
        }

    @staticmethod
    def sync_missing_expenses(db: Session):

        stats_rows = (
            db.query(MetaDailyStats)
            .order_by(MetaDailyStats.stats_date.desc())
            .limit(20)
            .all()
        )

        inserted = 0
        updated = 0

        for stats in stats_rows:

            reference = f"meta_{stats.stats_date}"

            existing = (
                db.query(Expense)
                .filter(Expense.external_reference == reference)
                .first()
            )

            if existing:

                existing.amount = stats.spend

                existing.expense_date = stats.stats_date

                existing.category = "marketing"

                existing.source = "meta"

                updated += 1

                continue

            expense = Expense(
                title="Meta Ads Spend",
                amount=stats.spend,
                category="marketing",
                source="meta",
                external_reference=reference,
                expense_date=stats.stats_date,
                created_at=pakistan_now(),
            )

            db.add(expense)

            inserted += 1

        db.commit()

        print(f"[META RECOVERY] Inserted {inserted} | Updated {updated}")

    @staticmethod
    def sync_historical_expenses(db: Session):

        stats_rows = db.query(MetaDailyStats).all()

        inserted = 0

        for stats in stats_rows:

            reference = f"meta_{stats.stats_date}"

            existing = (
                db.query(Expense)
                .filter(Expense.external_reference == reference)
                .first()
            )

            if existing:
                continue

            expense = Expense(
                title="Meta Ads Spend",
                amount=stats.spend,
                category="marketing",
                source="meta",
                external_reference=reference,
                expense_date=stats.stats_date,
                created_at=datetime.combine(stats.stats_date, datetime.min.time()),
            )

            db.add(expense)

            inserted += 1

        db.commit()

        return {
            "success": True,
            "inserted": inserted,
        }
