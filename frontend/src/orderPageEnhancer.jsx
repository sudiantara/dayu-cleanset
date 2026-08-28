import React from "react";
import { createRoot } from "react-dom/client";
import OrderListPage from "./OrderListPage.jsx";
import { CustomerPage, ServicePage, PaymentPage } from "./OperationsPages.jsx";
import FinancePage from "./FinancePage.jsx";

let root = null;
let host = null;
let activePage = "Dashboard";

function menuButtons() { return [...document.querySelectorAll(".menu .menu-item")]; }
function findMenu(label) { return menuButtons().find((button) => button.textContent?.trim().endsWith(label)); }
function setActiveMenu(label) { menuButtons().forEach((button) => button.classList.toggle("active", button.textContent?.trim().endsWith(label))); }

function ensureFinanceMenu(){
  const payment=findMenu("Pembayaran");
  if(!payment || findMenu("Keuangan")) return;
  const button=document.createElement("button");
  button.className="menu-item";
  button.type="button";
  button.innerHTML='<span class="menu-icon">▣</span><span>Keuangan</span>';
  payment.insertAdjacentElement("afterend",button);
}

function ensureHost(){const main=document.querySelector(".main-content");if(!main)return null;if(!host){host=document.createElement("div");host.id="workspace-host";main.parentNode.insertBefore(host,main.nextSibling);root=createRoot(host)}return main}
function openDashboard(){const main=ensureHost();activePage="Dashboard";if(host)host.style.display="none";if(main)main.style.display="block";setActiveMenu("Dashboard")}
function openWorkspace(label){const main=ensureHost();if(!main||!root)return;activePage=label;main.style.display="none";host.style.display="block";setActiveMenu(label);const onNewOrder=()=>document.querySelector(".main-content .primary-button")?.click();if(label==="Order")root.render(<OrderListPage onNewOrder={onNewOrder}/>);if(label==="Customer")root.render(<CustomerPage/>);if(label==="Service")root.render(<ServicePage/>);if(label==="Pembayaran")root.render(<PaymentPage/>);if(label==="Keuangan")root.render(<FinancePage/>)}
function bindNavigation(){ensureFinanceMenu();const labels=["Dashboard","Order","Customer","Service","Pembayaran","Keuangan"];labels.forEach(label=>{const button=findMenu(label);if(!button||button.dataset.workspaceBound==="1")return;button.dataset.workspaceBound="1";button.addEventListener("click",()=>label==="Dashboard"?openDashboard():openWorkspace(label))});setActiveMenu(activePage)}
export function installOrderPageEnhancer(){bindNavigation();const observer=new MutationObserver(bindNavigation);observer.observe(document.body,{childList:true,subtree:true})}
