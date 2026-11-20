from app.events.event_dispatcher import (
    EventDispatcher
)

from app.events.event_types import (
    EventTypes
)


class AnalyticsEvents:

    # ===================================
    # DASHBOARD UPDATED
    # ===================================

    @staticmethod
    async def dashboard_updated(
        data: dict
    ):

        await EventDispatcher.dispatch(

            EventTypes.DASHBOARD_UPDATED,

            data
        )