import React from "react";
import { createRoot } from "react-dom/client";
import OrderListPage from "./OrderListPage.jsx";
import { CustomerPage, ServicePage, PaymentPage } from "./OperationsPages.jsx";

let root = null;
let host = null;
let activePage = "Dashboard";

function menuButtons() {
  return [...document.querySelectorAll(".menu .menu-item")];
}

function findMenu(label) {
  return menuButtons().find((button) => button.textContent?.trim().endsWith(label));
}

function setActiveMenu(label) {
  menuButtons().forEach((button) => {
    button.classList.toggle("active", button.textContent?.trim().endsWith(label));
  });
}

function ensureHost() {
  const main = document.querySelector(".main-content");
  if (!main) return null;
  if (!host) {
    host = document.createElement("div");
    host.id = "workspace-host";
    main.parentNode.insertBefore(host, main.nextSibling);
    root = createRoot(host);
  }
  return main;
}

function openDashboard() {
  const main = ensureHost();
  activePage = "Dashboard";
  if (host) host.style.display = "none";
  if (main) main.style.display = "block";
  setActiveMenu("Dashboard");
}

function openWorkspace(label) {
  const main = ensureHost();
  if (!main || !root) return;
  activePage = label;
  main.style.display = "none";
  host.style.display = "block";
  setActiveMenu(label);

  const onNewOrder = () => {
    const dashboardNewOrder = document.querySelector(".main-content .primary-button");
    dashboardNewOrder?.click();
  };

  if (label === "Order") root.render(<OrderListPage onNewOrder={onNewOrder} />);
  if (label === "Customer") root.render(<CustomerPage />);
  if (label === "Service") root.render(<ServicePage />);
  if (label === "Pembayaran") root.render(<PaymentPage />);
}

function bindNavigation() {
  const labels = ["Dashboard", "Order", "Customer", "Service", "Pembayaran"];
  labels.forEach((label) => {
    const button = findMenu(label);
    if (!button || button.dataset.workspaceBound === "1") return;
    button.dataset.workspaceBound = "1";
    button.addEventListener("click", () => {
      if (label === "Dashboard") openDashboard();
      else openWorkspace(label);
    });
  });
  setActiveMenu(activePage);
}

export function installOrderPageEnhancer() {
  bindNavigation();
  const observer = new MutationObserver(bindNavigation);
  observer.observe(document.body, { childList: true, subtree: true });
}
