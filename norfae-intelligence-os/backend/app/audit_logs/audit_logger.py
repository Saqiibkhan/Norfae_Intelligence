import logging
import os

LOG_DIR = "app/audit_logs/log_files"

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

def get_logger(name: str, filename: str):

    logger = logging.getLogger(name)

    if not logger.handlers:

        file_handler = logging.FileHandler(
            f"{LOG_DIR}/{filename}"
        )

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )

        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        logger.setLevel(logging.INFO)

    return logger