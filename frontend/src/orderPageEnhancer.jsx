import React from "react";
import { createRoot } from "react-dom/client";
import OrderListPage from "./OrderListPage.jsx";
import { CustomerPage, ServicePage, PaymentPage } from "./OperationsPages.jsx";
import FinancePage from "./FinancePage.jsx";

let root=null,host=null,activePage="Dashboard";
function menuButtons(){return [...document.querySelectorAll(".menu .menu-item")]}function findMenu(label){return menuButtons().find(b=>b.textContent?.trim().endsWith(label))}function setActiveMenu(label){menuButtons().forEach(b=>b.classList.toggle("active",b.textContent?.trim().endsWith(label)))}function isAdmin(){return window.dayuCurrentUser?.role==="ADMIN"}
function ensureMenus(){const ops=findMenu("Operasional");ops?.remove();const existing=findMenu("Keuangan");if(!isAdmin()){existing?.remove();if(activePage==="Keuangan")openDashboard();return}const payment=findMenu("Pembayaran");if(!payment||existing)return;const b=document.createElement("button");b.className="menu-item";b.type="button";b.innerHTML='<span class="menu-icon">▣</span><span>Keuangan</span>';payment.insertAdjacentElement("afterend",b)}
function ensureHost(){const main=document.querySelector(".main-content");if(!main)return null;if(!host){host=document.createElement("div");host.id="workspace-host";main.parentNode.insertBefore(host,main.nextSibling);root=createRoot(host)}return main}
function openDashboard(){const main=ensureHost();activePage="Dashboard";if(host)host.style.display="none";if(main)main.style.display="block";setActiveMenu("Dashboard")}
function openWorkspace(label){if(label==="Keuangan"&&!isAdmin()){openDashboard();return}const main=ensureHost();if(!main||!root)return;activePage=label;main.style.display="none";host.style.display="block";setActiveMenu(label);const onNewOrder=()=>document.querySelector(".main-content .primary-button")?.click();if(label==="Order")root.render(<OrderListPage onNewOrder={onNewOrder}/>);if(label==="Customer")root.render(<CustomerPage/>);if(label==="Service")root.render(<ServicePage/>);if(label==="Pembayaran")root.render(<PaymentPage/>);if(label==="Keuangan")root.render(<FinancePage/>)}
function bindNavigation(){ensureMenus();const labels=["Dashboard","Order","Customer","Service","Pembayaran",...(isAdmin()?["Keuangan"]:[])];labels.forEach(label=>{const b=findMenu(label);if(!b||b.dataset.workspaceBound==="1")return;b.dataset.workspaceBound="1";b.addEventListener("click",()=>label==="Dashboard"?openDashboard():openWorkspace(label))});setActiveMenu(activePage)}
export function installOrderPageEnhancer(){bindNavigation();const observer=new MutationObserver(bindNavigation);observer.observe(document.body,{childList:true,subtree:true})}
