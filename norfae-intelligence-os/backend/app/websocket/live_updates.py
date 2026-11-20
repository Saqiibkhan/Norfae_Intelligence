import json

from app.websocket.connection_manager import manager


class LiveUpdateService:

    # ===================================
    # DASHBOARD UPDATE
    # ===================================

    @staticmethod
    async def dashboard_update(data: dict):

        payload = {"event": "dashboard_update", "data": data}

        await manager.broadcast(json.dumps(payload))

    # ===================================
    # ORDER UPDATE
    # ===================================

    @staticmethod
    async def order_update(data: dict):

        payload = {"event": "order_update", "data": data}

        await manager.broadcast(json.dumps(payload))

    # ===================================
    # SCALING ALERT
    # ===================================

    @staticmethod
    async def scaling_alert(data: dict):

        payload = {"event": "scaling_alert", "data": data}

        await manager.broadcast(json.dumps(payload))

    # ===================================
    # FATIGUE ALERT
    # ===================================

    @staticmethod
    async def fatigue_alert(data: dict):

        payload = {"event": "fatigue_alert", "data": data}

        await manager.broadcast(json.dumps(payload))
