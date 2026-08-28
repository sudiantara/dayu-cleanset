function replaceSelectWithSession(label, caption) {
  const select = label?.querySelector("select");
  const user = window.dayuCurrentUser;
  if (!label || !select || !user || label.dataset.sessionBound === "1") return;
  label.dataset.sessionBound = "1";
  select.style.display = "none";
  const badge = document.createElement("div");
  badge.className = "session-operator-badge";
  badge.innerHTML = `<strong>${user.name}</strong><span>${user.role}</span><small>${caption}</small>`;
  label.appendChild(badge);
}

function hideButtonByText(root, text) {
  const button = [...root.querySelectorAll("button")].find((item) => item.textContent?.trim() === text);
  if (button) button.style.display = "none";
}

function enhanceRoleActions() {
  const user = window.dayuCurrentUser;
  if (!user) return;

  const detailModal = document.querySelector(".detail-modal");
  if (detailModal) {
    const labels = [...detailModal.querySelectorAll("label")];
    labels.forEach((label) => {
      const text = label.childNodes[0]?.textContent?.trim() || label.textContent?.trim() || "";
      if (text.startsWith("Operator")) {
        replaceSelectWithSession(label, "Status akan dicatat atas user yang sedang login.");
      }
      if (text.startsWith("Diubah oleh")) {
        replaceSelectWithSession(label, "Perubahan akan dicatat atas user yang sedang login.");
      }
    });

    if (user.role !== "ADMIN") hideButtonByText(detailModal, "Delete");
    if (user.role === "STAFF") hideButtonByText(detailModal, "Edit Order");
  }

  if (user.role === "STAFF") {
    const newOrderButton = [...document.querySelectorAll("button")].find((button) => button.textContent?.trim() === "+ Order Baru");
    if (newOrderButton) newOrderButton.style.display = "none";
  }
}

export function installAuthUiEnhancer() {
  const observer = new MutationObserver(enhanceRoleActions);
  observer.observe(document.body, { childList: true, subtree: true });
  enhanceRoleActions();
}
