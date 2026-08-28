function injectReceiverField() {
  const modalBody = document.querySelector(".order-modal .modal-body");
  if (!modalBody || modalBody.querySelector("[data-receiver-enhancer]")) return;

  const sections = Array.from(modalBody.querySelectorAll(".form-section"));
  const locationSection = sections.find((section) =>
    section.querySelector(".form-section-title")?.textContent?.includes("Lokasi Menginap"),
  );
  if (!locationSection) return;

  const user = window.dayuCurrentUser;
  if (!user) return;

  const section = document.createElement("section");
  section.className = "form-section";
  section.dataset.receiverEnhancer = "true";

  const title = document.createElement("div");
  title.className = "form-section-title";
  title.textContent = "Penerimaan Order";

  const card = document.createElement("div");
  card.className = "receiver-session-card";
  card.innerHTML = `
    <div>
      <span>Diterima oleh</span>
      <strong>${user.name}</strong>
    </div>
    <div>
      <span>Role</span>
      <strong>${user.role}</strong>
    </div>
    <small>Identitas penerima dan jam penerimaan dicatat otomatis dari session login.</small>
  `;

  section.append(title, card);
  locationSection.parentNode.insertBefore(section, locationSection);
}

export function installOrderReceiverEnhancer() {
  const observer = new MutationObserver(() => {
    if (document.querySelector(".order-modal")) injectReceiverField();
  });

  observer.observe(document.body, { childList: true, subtree: true });
  injectReceiverField();
}