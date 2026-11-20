from app.audit_logs.audit_logger import (
    get_logger
)

logger = get_logger(
    "error_logger",
    "errors.log"
)

def log_error(message: str):

    logger.error(message)