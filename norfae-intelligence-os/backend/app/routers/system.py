from fastapi import APIRouter

from app.core.system_monitor import (
    SystemMonitor
)

router = APIRouter(
    prefix="/system",
    tags=["System"]
)


@router.get("/status")
def system_status():

    return (
        SystemMonitor
        .get_system_status()
    )