from app.events.event_dispatcher import EventDispatcher

from app.events.event_types import EventTypes

from app.websocket.live_updates import LiveUpdateService

# ===================================
# ORDER CREATED LISTENER
# ===================================


async def order_updated_listener(data):

    await LiveUpdateService.order_update(data)


# ===================================
# DASHBOARD UPDATED LISTENER
# ===================================


async def dashboard_updated_listener(data):

    await LiveUpdateService.dashboard_update(data)


# ===================================
# SCALING ALERT LISTENER
# ===================================


async def scaling_alert_listener(data):

    await LiveUpdateService.scaling_alert(data)


# ===================================
# REGISTER ALL LISTENERS
# ===================================


def register_event_listeners():

    EventDispatcher.register(EventTypes.ORDER_UPDATED, order_updated_listener)

    EventDispatcher.register(EventTypes.DASHBOARD_UPDATED, dashboard_updated_listener)

    EventDispatcher.register(EventTypes.SCALING_ALERT, scaling_alert_listener)
