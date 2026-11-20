class MetricsCollector:

    total_requests = 0

    total_websocket_connections = 0

    total_orders_processed = 0

    # ===================================
    # REQUEST COUNTER
    # ===================================

    @classmethod
    def increment_requests(cls):

        cls.total_requests += 1

    # ===================================
    # WEBSOCKET COUNTER
    # ===================================

    @classmethod
    def increment_websockets(cls):

        cls.total_websocket_connections += 1

    # ===================================
    # ORDER COUNTER
    # ===================================

    @classmethod
    def increment_orders(cls):

        cls.total_orders_processed += 1