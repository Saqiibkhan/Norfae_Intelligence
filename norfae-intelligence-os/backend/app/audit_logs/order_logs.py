from app.audit_logs.audit_logger import (
    get_logger
)

logger = get_logger(
    "order_logger",
    "orders.log"
)

def log_order_event(message: str):

    logger.info(message)