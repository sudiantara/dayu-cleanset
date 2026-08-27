import "./orderUxEnhancer.css";

function findFieldByLabelText(root, text) {
  const labels = [...root.querySelectorAll("label.field")];
  return labels.find((label) => {
    const span = label.querySelector(":scope > span");
    return span?.textContent?.trim() === text;
  });
}

function normalize(value) {
  return (value || "").toLowerCase().replace(/\s+/g, " ").trim();
}

function installCustomerSearch(modal) {
  const field = findFieldByLabelText(modal, "Customer *");
  const select = field?.querySelector("select");

  if (!field || !select || field.dataset.searchableCustomer === "1") return;

  field.dataset.searchableCustomer = "1";
  select.classList.add("native-customer-select-hidden");

  const wrapper = document.createElement("div");
  wrapper.className = "customer-search";
  wrapper.innerHTML = `
    <div class="customer-search-input-wrap">
      <span class="customer-search-icon">⌕</span>
      <input class="customer-search-input" type="search" autocomplete="off" placeholder="Cari nama / nomor WhatsApp..." />
      <button class="customer-search-clear" type="button" title="Hapus pilihan">×</button>
    </div>
    <div class="customer-selected-card" hidden></div>
    <div class="customer-search-results" hidden></div>
  `;

  field.insertBefore(wrapper, select);

  const input = wrapper.querySelector(".customer-search-input");
  const results = wrapper.querySelector(".customer-search-results");
  const selectedCard = wrapper.querySelector(".customer-selected-card");
  const clearButton = wrapper.querySelector(".customer-search-clear");

  function getCustomers() {
    return [...select.options]
      .filter((option) => option.value)
      .map((option) => {
        const parts = option.textContent.split("—");
        return {
          id: option.value,
          name: (parts[0] || "").trim(),
          phone: (parts.slice(1).join("—") || "").trim(),
          label: option.textContent.trim(),
        };
      });
  }

  function selectCustomer(customer) {
    select.value = customer.id;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    input.value = "";
    results.hidden = true;
    selectedCard.hidden = false;
    selectedCard.innerHTML = `
      <div>
        <strong>${customer.name}</strong>
        <span>${customer.phone || "Tanpa nomor"}</span>
      </div>
      <span class="customer-selected-check">✓ Dipilih</span>
    `;
  }

  function clearCustomer() {
    select.value = "";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    selectedCard.hidden = true;
    selectedCard.innerHTML = "";
    input.value = "";
    input.focus();
    renderResults("");
  }

  function renderResults(query) {
    const all = getCustomers();
    const q = normalize(query);
    const matches = q
      ? all.filter((customer) =>
          normalize(`${customer.name} ${customer.phone}`).includes(q),
        )
      : all.slice(0, 8);

    results.innerHTML = "";

    if (matches.length === 0) {
      const empty = document.createElement("div");
      empty.className = "customer-search-empty";
      empty.innerHTML = `
        <strong>Customer tidak ditemukan</strong>
        <span>Coba nama atau nomor lain, atau gunakan + Customer Baru.</span>
      `;
      results.appendChild(empty);
    } else {
      matches.slice(0, 8).forEach((customer) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "customer-result-item";
        button.innerHTML = `
          <span class="customer-result-name">${customer.name}</span>
          <span class="customer-result-phone">${customer.phone || "-"}</span>
        `;
        button.addEventListener("click", () => selectCustomer(customer));
        results.appendChild(button);
      });
    }

    results.hidden = false;
  }

  input.addEventListener("focus", () => renderResults(input.value));
  input.addEventListener("input", () => renderResults(input.value));
  clearButton.addEventListener("click", clearCustomer);

  document.addEventListener("mousedown", (event) => {
    if (!wrapper.contains(event.target)) results.hidden = true;
  });

  const current = getCustomers().find((customer) => customer.id === select.value);
  if (current) selectCustomer(current);
}

function installFinishTimeGuard(modal) {
  const field = findFieldByLabelText(modal, "Target Selesai *");
  const input = field?.querySelector('input[type="datetime-local"]');
  if (!input || input.dataset.finishGuard === "1") return;

  input.dataset.finishGuard = "1";

  function updateMin() {
    const now = new Date();
    now.setSeconds(0, 0);
    const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
    input.min = local;
  }

  updateMin();
  input.addEventListener("focus", updateMin);
}

function installDiscountWarning(modal) {
  if (modal.dataset.discountWarning === "1") return;
  modal.dataset.discountWarning = "1";

  const discountField = findFieldByLabelText(modal, "Diskon Nego (Rp)");
  const discountInput = discountField?.querySelector('input[type="number"]');
  const weightField = findFieldByLabelText(modal, "Berat Laundry (KG) *");
  const weightInput = weightField?.querySelector('input[type="number"]');
  if (!discountInput || !weightInput) return;

  const warning = document.createElement("div");
  warning.className = "discount-warning";
  warning.hidden = true;
  discountField.closest(".form-section")?.appendChild(warning);

  function updateWarning() {
    const weight = Number(weightInput.value) || 0;
    const express = modal.querySelector('input[name="service_speed"][value="EXPRESS"]')?.checked;
    const price = express ? 55000 : 30000;
    const subtotal = weight * price;
    const specialDiscount = Number(discountInput.value) || 0;

    if (subtotal > 0 && specialDiscount >= subtotal * 0.5) {
      const percent = Math.round((specialDiscount / subtotal) * 100);
      warning.hidden = false;
      warning.textContent = `⚠ Diskon nego sebesar ${percent}% dari subtotal. Pastikan nominal sudah benar sebelum menyimpan order.`;
    } else {
      warning.hidden = true;
      warning.textContent = "";
    }
  }

  modal.addEventListener("input", updateWarning);
  modal.addEventListener("change", updateWarning);
  updateWarning();
}

function enhanceOrderModal() {
  const modal = document.querySelector(".order-modal");
  if (!modal) return;

  installCustomerSearch(modal);
  installFinishTimeGuard(modal);
  installDiscountWarning(modal);
}

export function installOrderUxEnhancer() {
  const observer = new MutationObserver(enhanceOrderModal);
  observer.observe(document.body, { childList: true, subtree: true });
  enhanceOrderModal();
}
