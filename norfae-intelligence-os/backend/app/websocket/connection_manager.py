from fastapi import WebSocket


class ConnectionManager:

    def __init__(self):

        self.active_connections = []

    # ===================================
    # CONNECT
    # ===================================

    import os

    print(f"[PROCESS ID] {os.getpid()}")

    async def connect(self, websocket: WebSocket):

        await websocket.accept()

        self.active_connections.append(websocket)

        print(f"[WEBSOCKET CONNECTED] " f"Total: {len(self.active_connections)}")

    # ===================================
    # DISCONNECT
    # ===================================

    def disconnect(self, websocket: WebSocket):

        if websocket in self.active_connections:

            self.active_connections.remove(websocket)

        print(f"[WEBSOCKET DISCONNECTED] " f"Total: {len(self.active_connections)}")

    # ===================================
    # SEND PERSONAL
    # ===================================

    async def send_personal_message(self, message: str, websocket: WebSocket):

        await websocket.send_text(message)

    # ===================================
    # BROADCAST
    # ===================================

    import os

    print(f"[BROADCAST PROCESS ID] {os.getpid()}")

    async def broadcast(self, message: str):

        print(
            f"[WEBSOCKET BROADCAST] " f"Connections: " f"{len(self.active_connections)}"
        )

        dead_connections = []

        for connection in self.active_connections:

            try:

                await connection.send_text(message)

                print("[WEBSOCKET SENT]")

            except Exception as e:

                print(f"[WEBSOCKET ERROR] {e}")

                dead_connections.append(connection)

        # ===============================
        # CLEAN DEAD CONNECTIONS
        # ===============================

        for dead in dead_connections:

            self.disconnect(dead)


manager = ConnectionManager()
