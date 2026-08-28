import React from "react";
import { createRoot } from "react-dom/client";
import OrderListPage from "./OrderListPage.jsx";

let root = null;
let host = null;
let active = false;

function menuButtons() {
  return [...document.querySelectorAll(".menu .menu-item")];
}

function findMenu(label) {
  return menuButtons().find((button) => button.textContent?.trim().endsWith(label));
}

function setActiveMenu(label) {
  menuButtons().forEach((button) => {
    const isActive = button.textContent?.trim().endsWith(label);
    button.classList.toggle("active", isActive);
  });
}

function openOrderPage() {
  const main = document.querySelector(".main-content");
  if (!main) return;

  active = true;
  main.style.display = "none";
  setActiveMenu("Order");

  if (!host) {
    host = document.createElement("div");
    host.id = "order-list-host";
    main.parentNode.insertBefore(host, main.nextSibling);
    root = createRoot(host);
  }

  host.style.display = "block";
  root.render(
    <OrderListPage
      onNewOrder={() => {
        const dashboardNewOrder = document.querySelector(".main-content .primary-button");
        dashboardNewOrder?.click();
      }}
    />,
  );
}

function openDashboard() {
  const main = document.querySelector(".main-content");
  active = false;
  if (host) host.style.display = "none";
  if (main) main.style.display = "block";
  setActiveMenu("Dashboard");
}

function bindNavigation() {
  const orderButton = findMenu("Order");
  const dashboardButton = findMenu("Dashboard");

  if (orderButton && orderButton.dataset.orderPageBound !== "1") {
    orderButton.dataset.orderPageBound = "1";
    orderButton.addEventListener("click", openOrderPage);
  }

  if (dashboardButton && dashboardButton.dataset.orderPageBound !== "1") {
    dashboardButton.dataset.orderPageBound = "1";
    dashboardButton.addEventListener("click", openDashboard);
  }

  if (active) setActiveMenu("Order");
}

export function installOrderPageEnhancer() {
  bindNavigation();
  const observer = new MutationObserver(bindNavigation);
  observer.observe(document.body, { childList: true, subtree: true });
}
