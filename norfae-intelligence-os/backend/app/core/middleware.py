import time

from fastapi import Request

from app.core.logger import logger

from app.core.metrics import (
    MetricsCollector
)


async def logging_middleware(
    request: Request,
    call_next
):

    start_time = time.time()

    MetricsCollector.increment_requests()

    response = await call_next(
        request
    )

    process_time = (
        time.time() -
        start_time
    )

    logger.info(

        f"{request.method} "
        f"{request.url.path} "
        f"completed in "
        f"{process_time:.4f}s"
    )

    return response