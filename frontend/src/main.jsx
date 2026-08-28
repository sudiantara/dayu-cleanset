import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";
import AuthGate from "./AuthGate.jsx";
import { installOrderDetailEnhancer } from "./orderDetailEnhancer.jsx";
import { installOrderUxEnhancer } from "./orderUxEnhancer.js";
import { installOrderReceiverEnhancer } from "./orderReceiverEnhancer.js";
import { installAuthUiEnhancer } from "./authUiEnhancer.js";
import { installOrderPageEnhancer } from "./orderPageEnhancer.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <AuthGate>
      <App />
    </AuthGate>
  </StrictMode>,
);

installOrderDetailEnhancer();
installOrderUxEnhancer();
installOrderReceiverEnhancer();
installAuthUiEnhancer();
installOrderPageEnhancer();
