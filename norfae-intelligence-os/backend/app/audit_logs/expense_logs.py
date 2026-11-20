from app.audit_logs.audit_logger import (
    get_logger
)

logger = get_logger(
    "expense_logger",
    "expenses.log"
)

def log_expense_event(message: str):

    logger.info(message)