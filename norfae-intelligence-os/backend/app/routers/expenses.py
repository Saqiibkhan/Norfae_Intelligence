from fastapi import APIRouter, Depends, Query

from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.models.expense_model import Expense

from app.schemas.expense_schema import ExpenseCreate

from typing import List

from app.schemas.expense_schema import ExpenseResponse

from datetime import datetime, timedelta

from app.core.timezone import pakistan_now

from app.services.meta_expense_service import (
    MetaExpenseService,
)

router = APIRouter(prefix="/expenses", tags=["Expenses"])

# ===================================
# CREATE EXPENSE
# ===================================


@router.post("/", response_model=ExpenseResponse)
def create_expense(expense: ExpenseCreate, db: Session = Depends(get_db)):

    new_expense = Expense(
        title=expense.title,
        amount=expense.amount,
        category=expense.category,
        source=expense.source,
        payment_method=expense.payment_method,
        notes=expense.notes,
        is_recurring=expense.is_recurring,
        recurring_cycle=expense.recurring_cycle,
        expense_date=expense.created_at,
        created_at=(expense.created_at or pakistan_now()),
    )

    db.add(new_expense)

    db.commit()

    db.refresh(new_expense)

    return new_expense


# ===================================
# GET EXPENSES
# ===================================


@router.get("/", response_model=List[ExpenseResponse])
def get_expenses(
    filter_type: str = Query(default="today"),
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):

    query = db.query(Expense)

    # ===================================
    # Pakistan Time
    # ===================================

    pkt_now = pakistan_now()

    # ===================================
    # ALL
    # ===================================

    if filter_type == "all":

        pass

    # ===================================
    # TODAY
    # ===================================

    elif filter_type == "today":

        start = pkt_now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        end = start + timedelta(days=1)

        query = query.filter(
            Expense.expense_date >= start,
            Expense.expense_date < end,
        )

    # ===================================
    # YESTERDAY
    # ===================================

    elif filter_type == "yesterday":

        end = pkt_now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        start = end - timedelta(days=1)

        query = query.filter(
            Expense.expense_date >= start,
            Expense.expense_date < end,
        )

    # ===================================
    # WEEK
    # ===================================

    elif filter_type == "week":

        start = pkt_now - timedelta(days=pkt_now.weekday())

        start = start.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        query = query.filter(Expense.expense_date >= start)

    # ===================================
    # MONTH
    # ===================================

    elif filter_type == "month":

        start = pkt_now.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        query = query.filter(Expense.expense_date >= start)

    # ===================================
    # CUSTOM
    # ===================================

    elif filter_type == "custom" and start_date and end_date:

        start = datetime.strptime(
            start_date,
            "%Y-%m-%d",
        )

        end = datetime.strptime(
            end_date,
            "%Y-%m-%d",
        ) + timedelta(days=1)

        query = query.filter(
            Expense.expense_date >= start,
            Expense.expense_date < end,
        )

    return query.order_by(Expense.expense_date.desc()).all()


# ===================================
# DELETE EXPENSE
# ===================================


@router.delete("/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db)):

    expense = db.query(Expense).filter(Expense.id == expense_id).first()

    if not expense:

        return {"success": False, "message": "Expense not found"}

    db.delete(expense)

    db.commit()

    return {"success": True, "message": "Expense deleted successfully"}


# ===================================
# Sync Meta History
# ===================================


@router.post("/sync-meta-history")
def sync_meta_history(
    db: Session = Depends(get_db),
):

    return MetaExpenseService.sync_historical_expenses(db)
