import { useEffect, useState } from "react";
import "./OrderDetailModal.css";
import "./OrderOperations.css";
import { printInvoice58 } from "./invoicePrinter.js";

function rupiah(value) {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(Number(value) || 0);
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("id-ID", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function localDateTimeValue(value) {
  if (!value) return "";
  const date = new Date(value);
  const pad = (number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function notifyOrdersChanged() {
  window.dispatchEvent(new CustomEvent("dayu:orders-changed"));
}

const STATUS_OPTIONS = [
  "NEW", "RECEIVED", "WASHING", "DRYING", "IRONING", "READY",
  "DELIVERING", "COMPLETE", "PICKED_UP", "CANCELLED",
];

export function OrderDetailTrigger({ orderNumber, onChanged }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="order-link" onClick={() => setOpen(true)}>{orderNumber}</button>
      {open && (
        <OrderDetailModal
          orderNumber={orderNumber}
          onClose={() => setOpen(false)}
          onChanged={onChanged}
        />
      )}
    </>
  );
}

function OrderDetailModal({ orderNumber, onClose, onChanged }) {
  const [detail, setDetail] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [mode, setMode] = useState("VIEW");
  const [saving, setSaving] = useState(false);
  const [statusForm, setStatusForm] = useState({ status: "", note: "", changed_by: 1 });
  const [editForm, setEditForm] = useState(null);
  const [paymentForm, setPaymentForm] = useState({ payment_method: "CASH", notes: "Pelunasan order" });

  const currentUser = window.dayuCurrentUser;
  const canPay = ["ADMIN", "KASIR"].includes(String(currentUser?.role || "").toUpperCase());

  async function loadDetail() {
    setLoading(true);
    setError("");
    try {
      const [detailResponse, usersResponse] = await Promise.all([
        fetch(`/api/orders/${encodeURIComponent(orderNumber)}/overview-v2`),
        fetch("/api/users/active"),
      ]);
      const detailData = await detailResponse.json();
      const usersData = await usersResponse.json();
      if (!detailResponse.ok) throw new Error(detailData?.detail || "Gagal mengambil detail order.");
      if (!usersResponse.ok) throw new Error(usersData?.detail || "Gagal mengambil user.");

      setDetail(detailData);
      setUsers(Array.isArray(usersData) ? usersData : []);
      setStatusForm({ status: detailData.service.status, note: "", changed_by: currentUser?.id || detailData.receiver?.user_id || 1 });
      setEditForm({
        hotel_name: detailData.location.hotel_name || "",
        room_number: detailData.location.room_number || "",
        location_notes: detailData.location.location_notes || "",
        service_speed: detailData.service.speed,
        requested_finish_at: localDateTimeValue(detailData.service.requested_finish_at),
        total_weight: detailData.service.total_weight,
        instagram_followed: detailData.promo.instagram_followed,
        google_reviewed: detailData.promo.google_reviewed,
        special_discount: detailData.promo.special_discount,
        special_discount_reason: detailData.promo.special_discount_reason || "",
        notes: detailData.notes || "",
        updated_by: currentUser?.id || detailData.receiver?.user_id || 1,
      });
    } catch (loadError) {
      setError(loadError.message || "Gagal mengambil detail order.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadDetail(); }, [orderNumber]);

  async function refreshEverywhere() {
    await loadDetail();
    notifyOrdersChanged();
    if (onChanged) await onChanged();
  }

  async function updateStatus(event) {
    event.preventDefault();
    setSaving(true); setError(""); setMessage("");
    try {
      const response = await fetch(`/api/orders/${encodeURIComponent(orderNumber)}/status-v2`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(statusForm),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Gagal update status.");
      setMessage(`Status berhasil diubah menjadi ${data.new_status} oleh ${data.operator}.`);
      setMode("VIEW");
      await refreshEverywhere();
    } catch (actionError) {
      setError(actionError.message || "Gagal update status.");
    } finally { setSaving(false); }
  }

  async function saveEdit(event) {
    event.preventDefault();
    setSaving(true); setError(""); setMessage("");
    try {
      const payload = {
        ...editForm,
        total_weight: Number(editForm.total_weight),
        special_discount: Number(editForm.special_discount) || 0,
        requested_finish_at: editForm.requested_finish_at ? new Date(editForm.requested_finish_at).toISOString() : null,
      };
      const response = await fetch(`/api/orders/${encodeURIComponent(orderNumber)}/edit-v2`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Gagal mengedit order.");
      setMessage(`Order diperbarui oleh ${data.updated_by}.`);
      setMode("VIEW");
      await refreshEverywhere();
    } catch (actionError) {
      setError(actionError.message || "Gagal mengedit order.");
    } finally { setSaving(false); }
  }

  async function markPaid(event) {
    event.preventDefault();
    setSaving(true); setError(""); setMessage("");
    try {
      const response = await fetch(`/api/orders/${encodeURIComponent(orderNumber)}/mark-paid`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          payment_method: paymentForm.payment_method,
          reference_number: null,
          notes: paymentForm.notes || "Pelunasan order",
          created_by: currentUser?.id || 1,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Gagal mencatat pembayaran.");
      setMessage(`Pembayaran berhasil. Order ${orderNumber} sekarang PAID.`);
      setMode("VIEW");
      await refreshEverywhere();
    } catch (actionError) {
      setError(actionError.message || "Gagal mencatat pembayaran.");
    } finally { setSaving(false); }
  }

  async function deleteOrder() {
    const reason = window.prompt(`Alasan menghapus ${orderNumber}:`);
    if (reason === null) return;
    if (!window.confirm(`Hapus order ${orderNumber}? Tindakan ini permanen dan hanya boleh untuk order tanpa pembayaran.`)) return;
    setSaving(true); setError("");
    try {
      const response = await fetch(`/api/orders/${encodeURIComponent(orderNumber)}/delete-v2`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor_user_id: currentUser?.id || 1, reason }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Gagal menghapus order.");
      notifyOrdersChanged();
      if (onChanged) await onChanged();
      onClose();
    } catch (actionError) {
      setError(actionError.message || "Gagal menghapus order.");
      setSaving(false);
    }
  }

  function editField(field, value) { setEditForm((current) => ({ ...current, [field]: value })); }

  return (
    <div className="detail-backdrop" onMouseDown={onClose}>
      <div className="detail-modal" onMouseDown={(event) => event.stopPropagation()}>
        <div className="detail-header">
          <div><span className="detail-kicker">DETAIL ORDER</span><h2>{orderNumber}</h2></div>
          <button type="button" className="detail-close" onClick={onClose}>×</button>
        </div>

        <div className="detail-body">
          {loading && <div className="detail-message">Memuat detail order...</div>}
          {error && <div className="detail-message error">{error}</div>}
          {message && <div className="ops-success">{message}</div>}

          {detail && !loading && (
            <>
              <div className="detail-status-row">
                <span className={`detail-badge status-${detail.service.status.toLowerCase()}`}>{detail.service.status}</span>
                <span className={`detail-badge payment-${detail.billing.payment_status.toLowerCase()}`}>{detail.billing.payment_status}</span>
                <span className="detail-created">Dibuat {formatDate(detail.created_at)}</span>
              </div>

              <div className="ops-toolbar">
                <button type="button" onClick={() => setMode(mode === "EDIT" ? "VIEW" : "EDIT")}>Edit Order</button>
                <button type="button" onClick={() => setMode(mode === "STATUS" ? "VIEW" : "STATUS")}>Update Status</button>
                {canPay && detail.billing.payment_status !== "PAID" && (
                  <button type="button" className="payment-action" onClick={() => setMode(mode === "PAYMENT" ? "VIEW" : "PAYMENT")}>Bayar / Tandai Lunas</button>
                )}
                <button type="button" onClick={() => printInvoice58(detail)}>Print Invoice 58mm</button>
                <button type="button" className="danger" onClick={deleteOrder} disabled={saving}>Delete</button>
              </div>

              {mode === "PAYMENT" && canPay && detail.billing.payment_status !== "PAID" && (
                <form className="ops-panel payment-panel" onSubmit={markPaid}>
                  <h3>Pelunasan Order</h3>
                  <p className="payment-help">Sisa yang akan dibayar: <strong>{rupiah(detail.billing.remaining_amount)}</strong></p>
                  <div className="ops-grid">
                    <label>Metode Pembayaran
                      <select value={paymentForm.payment_method} onChange={(e) => setPaymentForm({ ...paymentForm, payment_method: e.target.value })}>
                        <option value="CASH">CASH</option>
                        <option value="QRIS">QRIS</option>
                        <option value="TRANSFER">TRANSFER</option>
                      </select>
                    </label>
                    <label>Dicatat oleh
                      <div className="session-operator-badge"><strong>{currentUser?.name || "User"}</strong><span>{currentUser?.role || "-"}</span></div>
                    </label>
                    <label className="ops-full">Catatan
                      <input value={paymentForm.notes} onChange={(e) => setPaymentForm({ ...paymentForm, notes: e.target.value })} placeholder="Pelunasan saat pengambilan" />
                    </label>
                  </div>
                  <button type="submit" className="ops-primary" disabled={saving}>{saving ? "Memproses..." : `Bayar ${rupiah(detail.billing.remaining_amount)}`}</button>
                </form>
              )}

              {mode === "STATUS" && (
                <form className="ops-panel" onSubmit={updateStatus}>
                  <h3>Update Status Laundry</h3>
                  <div className="ops-grid">
                    <label>Status<select value={statusForm.status} onChange={(e) => setStatusForm({ ...statusForm, status: e.target.value })}>{STATUS_OPTIONS.map((status) => <option key={status} value={status}>{status}</option>)}</select></label>
                    <label>Operator<select value={statusForm.changed_by} onChange={(e) => setStatusForm({ ...statusForm, changed_by: Number(e.target.value) })}>{users.map((user) => <option key={user.id} value={user.id}>{user.name} ({user.role})</option>)}</select></label>
                    <label className="ops-full">Catatan Status<input value={statusForm.note} onChange={(e) => setStatusForm({ ...statusForm, note: e.target.value })} placeholder="Contoh: Cucian masuk mesin 1" /></label>
                  </div>
                  <button type="submit" className="ops-primary" disabled={saving}>{saving ? "Menyimpan..." : "Simpan Status"}</button>
                </form>
              )}

              {mode === "EDIT" && editForm && (
                <form className="ops-panel" onSubmit={saveEdit}>
                  <h3>Edit Order</h3>
                  <div className="ops-grid">
                    <label>Hotel / Villa<input value={editForm.hotel_name} onChange={(e) => editField("hotel_name", e.target.value)} required /></label>
                    <label>Room<input value={editForm.room_number} onChange={(e) => editField("room_number", e.target.value)} /></label>
                    <label>Service<select value={editForm.service_speed} onChange={(e) => editField("service_speed", e.target.value)}><option>NORMAL</option><option>EXPRESS</option></select></label>
                    <label>Berat KG<input type="number" min="0.1" step="0.1" value={editForm.total_weight} onChange={(e) => editField("total_weight", e.target.value)} /></label>
                    <label>Target Selesai<input type="datetime-local" value={editForm.requested_finish_at} onChange={(e) => editField("requested_finish_at", e.target.value)} /></label>
                    <label>Diskon Nego<input type="number" min="0" step="1000" value={editForm.special_discount} onChange={(e) => editField("special_discount", e.target.value)} /></label>
                    <label className="ops-check"><input type="checkbox" checked={editForm.instagram_followed} onChange={(e) => editField("instagram_followed", e.target.checked)} /> Follow Instagram</label>
                    <label className="ops-check"><input type="checkbox" checked={editForm.google_reviewed} onChange={(e) => editField("google_reviewed", e.target.checked)} /> Google Review</label>
                    <label className="ops-full">Alasan Diskon<input value={editForm.special_discount_reason} onChange={(e) => editField("special_discount_reason", e.target.value)} /></label>
                    <label className="ops-full">Catatan Lokasi<input value={editForm.location_notes} onChange={(e) => editField("location_notes", e.target.value)} /></label>
                    <label className="ops-full">Catatan Laundry<input value={editForm.notes} onChange={(e) => editField("notes", e.target.value)} /></label>
                    <label>Diubah oleh<select value={editForm.updated_by} onChange={(e) => editField("updated_by", Number(e.target.value))}>{users.map((user) => <option key={user.id} value={user.id}>{user.name} ({user.role})</option>)}</select></label>
                  </div>
                  <button type="submit" className="ops-primary" disabled={saving}>{saving ? "Menyimpan..." : "Simpan Perubahan"}</button>
                </form>
              )}

              <div className="detail-grid">
                <section className="detail-card"><h3>Customer</h3><dl>
                  <div><dt>Nama</dt><dd>{detail.customer.name}</dd></div><div><dt>WhatsApp / HP</dt><dd>{detail.customer.phone}</dd></div>
                  <div><dt>Diterima Oleh</dt><dd>{detail.receiver?.name || "System"}</dd></div><div><dt>Jam Terima</dt><dd>{formatDate(detail.receiver?.received_at || detail.created_at)}</dd></div>
                </dl></section>
                <section className="detail-card"><h3>Lokasi Menginap</h3><dl>
                  <div><dt>Hotel / Villa</dt><dd>{detail.location.hotel_name || "-"}</dd></div><div><dt>Room</dt><dd>{detail.location.room_number || "-"}</dd></div><div><dt>Catatan</dt><dd>{detail.location.location_notes || "-"}</dd></div>
                </dl></section>
                <section className="detail-card"><h3>Laundry</h3><dl>
                  <div><dt>Service</dt><dd>{detail.service.speed}</dd></div><div><dt>Berat</dt><dd>{detail.service.total_weight} KG</dd></div><div><dt>Target Selesai</dt><dd>{formatDate(detail.service.requested_finish_at)}</dd></div><div><dt>Catatan Laundry</dt><dd>{detail.notes || "-"}</dd></div>
                </dl></section>
                <section className="detail-card"><h3>Promo</h3><dl>
                  <div><dt>Follow Instagram</dt><dd>{detail.promo.instagram_followed ? "YES" : "NO"}</dd></div><div><dt>Google Review</dt><dd>{detail.promo.google_reviewed ? "YES" : "NO"}</dd></div>
                  {Number(detail.promo.promo_discount) > 0 && <div><dt>Promo 5%</dt><dd>- {rupiah(detail.promo.promo_discount)}</dd></div>}
                  {Number(detail.promo.special_discount) > 0 && <><div><dt>Diskon Nego</dt><dd>- {rupiah(detail.promo.special_discount)}</dd></div><div><dt>Alasan Nego</dt><dd>{detail.promo.special_discount_reason || "-"}</dd></div></>}
                </dl></section>
              </div>

              <section className="detail-billing">
                <h3>Rincian Pembayaran</h3>
                <div className="billing-line"><span>Subtotal</span><strong>{rupiah(detail.billing.subtotal)}</strong></div>
                {Number(detail.promo.promo_discount) > 0 && <div className="billing-line discount"><span>Promo 5%</span><strong>- {rupiah(detail.promo.promo_discount)}</strong></div>}
                {Number(detail.promo.special_discount) > 0 && <div className="billing-line discount"><span>Diskon Nego</span><strong>- {rupiah(detail.promo.special_discount)}</strong></div>}
                {Number(detail.billing.discount) > 0 && <div className="billing-line total-discount"><span>Total Diskon</span><strong>- {rupiah(detail.billing.discount)}</strong></div>}
                <div className="billing-line grand-total"><span>Total</span><strong>{rupiah(detail.billing.total)}</strong></div>
                <div className="billing-line"><span>Sudah Dibayar</span><strong>{rupiah(detail.billing.paid_amount)}</strong></div>
                <div className="billing-line remaining"><span>Sisa</span><strong>{rupiah(detail.billing.remaining_amount)}</strong></div>
              </section>

              <div className="detail-grid lower-grid">
                <section className="detail-card"><h3>Riwayat Status</h3>{detail.history.length === 0 ? <p className="detail-empty">Belum ada riwayat.</p> : <div className="detail-timeline">{detail.history.map((item) => <div className="timeline-item" key={item.id}><div className="timeline-dot" /><div><strong>{item.status}</strong><p>{item.note || "-"}</p><small>{formatDate(item.created_at)} · {item.operator || "System"}</small></div></div>)}</div>}</section>
                <section className="detail-card"><h3>Riwayat Pembayaran</h3>{detail.payments.length === 0 ? <p className="detail-empty">Belum ada pembayaran.</p> : <div className="payment-list">{detail.payments.map((payment) => <div className="payment-item" key={payment.id}><div><strong>{payment.payment_method}</strong><small>{formatDate(payment.created_at)} · {payment.operator || "System"}</small></div><strong>{rupiah(payment.amount)}</strong></div>)}</div>}</section>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
