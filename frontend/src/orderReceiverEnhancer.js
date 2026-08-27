let selectedReceiverId = 1;
let activeUsers = [];
let fetchWrapped = false;

async function loadUsers() {
  try {
    const response = await window.fetch("/api/users/active");
    if (!response.ok) return;
    const data = await response.json();
    if (Array.isArray(data) && data.length) {
      activeUsers = data;
      if (!activeUsers.some((user) => Number(user.id) === Number(selectedReceiverId))) {
        selectedReceiverId = Number(activeUsers[0].id);
      }
    }
  } catch (error) {
    console.error("Receiver users load error", error);
  }
}

function wrapFetch() {
  if (fetchWrapped) return;
  fetchWrapped = true;
  const originalFetch = window.fetch.bind(window);

  window.fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input?.url || "";
    const method = String(init?.method || "GET").toUpperCase();

    if (method === "POST" && /\/api\/orders\/?$/.test(url) && init?.body) {
      try {
        const payload = JSON.parse(init.body);
        payload.created_by = Number(selectedReceiverId) || 1;
        init = { ...init, body: JSON.stringify(payload) };
      } catch (error) {
        console.error("Unable to attach receiver to order", error);
      }
    }

    return originalFetch(input, init);
  };
}

function injectReceiverField() {
  const modalBody = document.querySelector(".order-modal .modal-body");
  if (!modalBody || modalBody.querySelector("[data-receiver-enhancer]")) return;

  const sections = Array.from(modalBody.querySelectorAll(".form-section"));
  const locationSection = sections.find((section) =>
    section.querySelector(".form-section-title")?.textContent?.includes("Lokasi Menginap"),
  );
  if (!locationSection) return;

  const section = document.createElement("section");
  section.className = "form-section";
  section.dataset.receiverEnhancer = "true";

  const title = document.createElement("div");
  title.className = "form-section-title";
  title.textContent = "Penerimaan Order";

  const grid = document.createElement("div");
  grid.className = "form-grid two-column";

  const label = document.createElement("label");
  label.className = "field field-full";
  const span = document.createElement("span");
  span.textContent = "Diterima oleh *";
  const select = document.createElement("select");
  select.required = true;

  activeUsers.forEach((user) => {
    const option = document.createElement("option");
    option.value = user.id;
    option.textContent = `${user.name} (${user.role})`;
    if (Number(user.id) === Number(selectedReceiverId)) option.selected = true;
    select.appendChild(option);
  });

  select.addEventListener("change", () => {
    selectedReceiverId = Number(select.value) || 1;
  });

  const small = document.createElement("small");
  small.textContent = "Nama user ini akan tercatat sebagai penerima order beserta jam penerimaan.";

  label.append(span, select, small);
  grid.appendChild(label);
  section.append(title, grid);
  locationSection.parentNode.insertBefore(section, locationSection);
}

export function installOrderReceiverEnhancer() {
  wrapFetch();
  loadUsers().then(injectReceiverField);

  const observer = new MutationObserver(() => {
    if (document.querySelector(".order-modal")) {
      if (!activeUsers.length) {
        loadUsers().then(injectReceiverField);
      } else {
        injectReceiverField();
      }
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });
}
