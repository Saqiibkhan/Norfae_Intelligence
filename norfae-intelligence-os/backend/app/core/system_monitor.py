from app.core.metrics import (
    MetricsCollector
)


class SystemMonitor:

    # ===================================
    # SYSTEM STATUS
    # ===================================

    @staticmethod
    def get_system_status():

        return {

            "total_requests": (
                MetricsCollector
                .total_requests
            ),

            "total_websocket_connections": (

                MetricsCollector
                .total_websocket_connections
            ),

            "total_orders_processed": (

                MetricsCollector
                .total_orders_processed
            )
        }