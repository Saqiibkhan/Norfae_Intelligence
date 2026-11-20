from app.events.event_dispatcher import EventDispatcher

from app.events.event_types import EventTypes


class OrderEvents:

    # ===================================
    # ORDER CREATED
    # ===================================

    @staticmethod
    async def order_created(order_data: dict):

        await EventDispatcher.dispatch(EventTypes.ORDER_CREATED, order_data)

    # ===================================
    # ORDER UPDATED
    # ===================================

    @staticmethod
    async def order_updated(order_data: dict):

        await EventDispatcher.dispatch(EventTypes.ORDER_UPDATED, order_data)
