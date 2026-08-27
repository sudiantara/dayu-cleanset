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

function enhanceDetailOperations() {
  const modal = document.querySelector(".detail-modal");
  const user = window.dayuCurrentUser;
  if (!modal || !user) return;

  const labels = [...modal.querySelectorAll("label")];
  labels.forEach((label) => {
    const text = label.childNodes[0]?.textContent?.trim() || label.textContent?.trim() || "";
    if (text.startsWith("Operator")) {
      replaceSelectWithSession(label, "Status akan dicatat atas user yang sedang login.");
    }
    if (text.startsWith("Diubah oleh")) {
      replaceSelectWithSession(label, "Perubahan akan dicatat atas user yang sedang login.");
    }
  });

  const deleteButton = [...modal.querySelectorAll("button")].find((button) => button.textContent?.trim() === "Delete");
  if (deleteButton && user.role !== "ADMIN") deleteButton.style.display = "none";
}

export function installAuthUiEnhancer() {
  const observer = new MutationObserver(enhanceDetailOperations);
  observer.observe(document.body, { childList: true, subtree: true });
  enhanceDetailOperations();
}