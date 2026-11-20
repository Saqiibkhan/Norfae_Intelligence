from app.websocket.live_updates import (
    LiveUpdateService
)


class NotificationOrchestrator:

    # ===================================
    # SEND ALERT
    # ===================================

    @staticmethod
    async def send_alert(
        alert_data: dict
    ):

        await (
            LiveUpdateService
            .scaling_alert(
                alert_data
            )
        )