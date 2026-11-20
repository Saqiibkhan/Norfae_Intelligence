from app.websocket.live_updates import (
    LiveUpdateService
)


class DashboardOrchestrator:

    # ===================================
    # UPDATE DASHBOARD
    # ===================================

    @staticmethod
    async def update_dashboard(
        dashboard_data: dict
    ):

        await (
            LiveUpdateService
            .dashboard_update(
                dashboard_data
            )
        )