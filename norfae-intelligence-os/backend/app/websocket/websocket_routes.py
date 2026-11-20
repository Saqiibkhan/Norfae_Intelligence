from fastapi import APIRouter, WebSocket


router = APIRouter()
_DISABLED_REASON = (
    "Live streams are unavailable until WebSocket authentication and business scoping are implemented."
)


async def _reject_unscoped_connection(websocket: WebSocket) -> None:
    # Close before accept so no unauthenticated stream is established.
    await websocket.close(code=1008, reason=_DISABLED_REASON)


@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await _reject_unscoped_connection(websocket)


@router.websocket("/ws/orders")
async def websocket_orders(websocket: WebSocket):
    await _reject_unscoped_connection(websocket)


@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    await _reject_unscoped_connection(websocket)
