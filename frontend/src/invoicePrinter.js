function money(value) {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(Number(value) || 0);
}

function dateTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("id-ID", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function escapeHtml(value) {
  return String(value ?? "-")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function printInvoice58(detail) {
  const popup = window.open("", "dayu-invoice", "width=420,height=720");
  if (!popup) {
    throw new Error("Popup diblokir browser. Izinkan popup untuk print invoice.");
  }

  const html = `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>${escapeHtml(detail.order_number)}</title>
<style>
@page { size: 58mm auto; margin: 2mm; }
* { box-sizing: border-box; }
body { width: 54mm; margin: 0 auto; font-family: Arial, sans-serif; font-size: 10px; color: #000; }
.center { text-align: center; }
h1 { font-size: 15px; margin: 0 0 2px; }
.muted { font-size: 9px; }
.sep { border-top: 1px dashed #000; margin: 7px 0; }
.row { display: flex; justify-content: space-between; gap: 8px; margin: 3px 0; }
.row span:first-child { flex: 1; }
.row strong { text-align: right; }
.wrap { word-break: break-word; }
.total { font-size: 12px; font-weight: 700; }
.footer { margin-top: 10px; text-align: center; font-size: 9px; }
</style>
</head>
<body>
  <div class="center">
    <h1>DAYU CLEANSET</h1>
    <div>Laundry</div>
    <div class="muted">${escapeHtml(detail.order_number)}</div>
  </div>

  <div class="sep"></div>
  <div class="row"><span>Customer</span><strong>${escapeHtml(detail.customer.name)}</strong></div>
  <div class="row"><span>WhatsApp</span><strong>${escapeHtml(detail.customer.phone)}</strong></div>
  <div class="row"><span>Hotel/Villa</span><strong>${escapeHtml(detail.location.hotel_name)}</strong></div>
  <div class="row"><span>Room</span><strong>${escapeHtml(detail.location.room_number)}</strong></div>
  <div class="row"><span>Diterima</span><strong>${escapeHtml(detail.receiver?.name || "System")}</strong></div>
  <div class="row"><span>Jam Terima</span><strong>${escapeHtml(dateTime(detail.receiver?.received_at || detail.created_at))}</strong></div>

  <div class="sep"></div>
  <div class="row"><span>Service</span><strong>${escapeHtml(detail.service.speed)}</strong></div>
  <div class="row"><span>Berat</span><strong>${escapeHtml(detail.service.total_weight)} KG</strong></div>
  <div class="row"><span>Target</span><strong>${escapeHtml(dateTime(detail.service.requested_finish_at))}</strong></div>

  <div class="sep"></div>
  <div class="row"><span>Subtotal</span><strong>${escapeHtml(money(detail.billing.subtotal))}</strong></div>
  <div class="row"><span>Promo 5%</span><strong>- ${escapeHtml(money(detail.promo.promo_discount))}</strong></div>
  <div class="row"><span>Diskon Nego</span><strong>- ${escapeHtml(money(detail.promo.special_discount))}</strong></div>
  <div class="row total"><span>TOTAL</span><strong>${escapeHtml(money(detail.billing.total))}</strong></div>
  <div class="row"><span>Status Bayar</span><strong>${escapeHtml(detail.billing.payment_status)}</strong></div>
  <div class="row"><span>Sisa</span><strong>${escapeHtml(money(detail.billing.remaining_amount))}</strong></div>

  <div class="sep"></div>
  <div class="wrap">Catatan: ${escapeHtml(detail.notes || "-")}</div>
  <div class="footer">Terima kasih telah menggunakan Dayu Cleanset Laundry.</div>

<script>
window.onload = () => { window.print(); };
</script>
</body>
</html>`;

  popup.document.open();
  popup.document.write(html);
  popup.document.close();
}
