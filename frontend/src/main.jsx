import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";
import { installOrderDetailEnhancer } from "./orderDetailEnhancer.jsx";
import { installOrderUxEnhancer } from "./orderUxEnhancer.js";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

installOrderDetailEnhancer();
installOrderUxEnhancer();
