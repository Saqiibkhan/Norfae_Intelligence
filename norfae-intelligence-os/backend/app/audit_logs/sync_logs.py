from app.audit_logs.audit_logger import (
    get_logger
)

logger = get_logger(
    "sync_logger",
    "sync.log"
)

def log_sync_event(message: str):

    logger.info(message)