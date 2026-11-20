import { createRoot } from "react-dom/client";

import "./index.css";

import App from "./App.jsx";

import { Toaster } from "sonner";

///import websocketService from "./services/websocketService";

///websocketService.connect();

createRoot(document.getElementById("root")).render(
  <>
    <App />

    <Toaster richColors position="top-right" duration={3000} closeButton />
  </>,
);
