from app.audit_logs.audit_logger import (
    get_logger
)

logger = get_logger(
    "profit_logger",
    "profits.log"
)

def log_profit_event(message: str):

    logger.info(message)