import { createRoot } from "react-dom/client";
import { OrderDetailTrigger } from "./OrderDetailModal.jsx";

function enhanceOrderLinks() {
  const candidates = document.querySelectorAll("td strong:not([data-order-detail-ready])");

  candidates.forEach((element) => {
    const orderNumber = element.textContent?.trim();

    if (!orderNumber || !orderNumber.startsWith("DL-")) {
      return;
    }

    element.dataset.orderDetailReady = "true";
    element.textContent = "";

    createRoot(element).render(
      <OrderDetailTrigger orderNumber={orderNumber} />,
    );
  });
}

export function installOrderDetailEnhancer() {
  enhanceOrderLinks();

  const observer = new MutationObserver(() => {
    enhanceOrderLinks();
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });

  return () => observer.disconnect();
}
