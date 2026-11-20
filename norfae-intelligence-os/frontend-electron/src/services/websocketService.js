class WebSocketService {
  constructor() {
    this.socket = null;
  }

  connect() {
    if (this.socket) {
      return;
    }

    this.socket = new WebSocket("ws://localhost:8000/ws/orders");

    this.socket.onopen = () => {
      console.log("[WEBSOCKET CONNECTED]");
    };

    this.socket.onmessage = (event) => {
      const message = JSON.parse(event.data);

      console.log("[WEBSOCKET MESSAGE]", message);

      window.dispatchEvent(
        new CustomEvent("order_update", {
          detail: message,
        }),
      );
    };

    this.socket.onclose = () => {
      console.log("[WEBSOCKET CLOSED]");

      this.socket = null;
    };

    this.socket.onerror = (error) => {
      console.error("[WEBSOCKET ERROR]", error);
    };
  }
}

export default new WebSocketService();
