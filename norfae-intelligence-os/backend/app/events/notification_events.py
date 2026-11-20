from app.events.event_dispatcher import (
    EventDispatcher
)

from app.events.event_types import (
    EventTypes
)


class NotificationEvents:

    # ===================================
    # SCALING ALERT
    # ===================================

    @staticmethod
    async def scaling_alert(
        data: dict
    ):

        await EventDispatcher.dispatch(

            EventTypes.SCALING_ALERT,

            data
        )