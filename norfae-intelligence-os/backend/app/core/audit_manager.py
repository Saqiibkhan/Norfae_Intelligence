from datetime import datetime


class AuditManager:

    # ===================================
    # CREATE AUDIT LOG
    # ===================================

    @staticmethod
    def log_event(
        event_type: str,
        data: dict
    ):

        print({

            "timestamp": (
                datetime.utcnow()
            ),

            "event_type": event_type,

            "data": data
        })