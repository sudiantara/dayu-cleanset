import { useEffect, useMemo, useState } from "react";
import "./CustomerCommunicationModal.css";

const TEMPLATE_LABELS = {
  ORDER_RECEIVED: "Order Diterima",
  READY: "Laundry Ready",
  PAYMENT_REMINDER: "Reminder Pembayaran",
  PICKUP_REMINDER: "Reminder Pickup",
  DELIVERY: "Sedang Delivery",
  THANK_YOU: "Terima Kasih",
};

function formatDate(value) {
  return value ? new Date(value).toLocaleString("id-ID", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "-";
}

export function CustomerCommunicationTrigger({ orderNumber, compact = false, onChanged }) {
  const [open, setOpen] = useState(false);
  return <>
    <button type="button" className={compact ? "comm-trigger compact" : "comm-trigger"} onClick={() => setOpen(true)}>WhatsApp</button>
    {open && <CustomerCommunicationModal orderNumber={orderNumber} onClose={() => setOpen(false)} onChanged={onChanged} />}
  </>;
}

export default function CustomerCommunicationModal({ orderNumber, onClose, onChanged }) {
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState("READY");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true); setError("");
    try {
      const response = await fetch(`/api/orders/${encodeURIComponent(orderNumber)}/communication-v1`);
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Gagal mengambil komunikasi customer");
      setData(body);
      const preferred = body.status === "READY" && body.payment_status !== "PAID" ? "PAYMENT_REMINDER"
        : body.status === "READY" ? "READY"
        : body.status === "DELIVERING" ? "DELIVERY"
        : body.status === "COMPLETE" ? "THANK_YOU"
        : "ORDER_RECEIVED";
      setSelected(preferred);
      setMessage(body.templates?.[preferred] || "");
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [orderNumber]);
  useEffect(() => { if (data?.templates?.[selected]) setMessage(data.templates[selected]); }, [selected]);

  const waUrl = useMemo(() => data?.whatsapp_number ? `https://wa.me/${data.whatsapp_number}?text=${encodeURIComponent(message)}` : "", [data, message]);

  async function logAndOpen() {
    if (!message.trim() || !waUrl) return;
    setSaving(true); setError("");
    try {
      const response = await fetch(`/api/orders/${encodeURIComponent(orderNumber)}/communication-v1`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_type: selected, message, channel: "WHATSAPP", status: "OPENED" }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Gagal mencatat komunikasi");
      window.open(waUrl, "_blank", "noopener,noreferrer");
      await load();
      window.dispatchEvent(new CustomEvent("dayu:orders-changed"));
      if (onChanged) await onChanged();
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  }

  async function copyMessage() {
    try { await navigator.clipboard.writeText(message); }
    catch { setError("Gagal copy pesan. Silakan copy manual."); }
  }

  return <div className="comm-backdrop" onMouseDown={onClose}>
    <div className="comm-modal" onMouseDown={e => e.stopPropagation()}>
      <div className="comm-header"><div><span>CUSTOMER COMMUNICATION</span><h2>{orderNumber}</h2></div><button onClick={onClose}>×</button></div>
      {loading ? <div className="comm-loading">Memuat...</div> : data && <div className="comm-body">
        {error && <div className="comm-error">{error}</div>}
        <div className="comm-customer"><div><strong>{data.customer}</strong><span>{data.phone}</span></div><div><span>Status</span><strong>{data.status}</strong></div><div><span>Pembayaran</span><strong>{data.payment_status}</strong></div></div>
        <label className="comm-field">Template<select value={selected} onChange={e => setSelected(e.target.value)}>{Object.keys(data.templates || {}).map(key => <option key={key} value={key}>{TEMPLATE_LABELS[key] || key}</option>)}</select></label>
        <label className="comm-field">Pesan<textarea rows="7" value={message} onChange={e => setMessage(e.target.value)} /></label>
        <div className="comm-actions"><button onClick={copyMessage}>Copy Pesan</button><button className="comm-wa" disabled={saving || !data.whatsapp_number} onClick={logAndOpen}>{saving ? "Membuka..." : "Buka WhatsApp"}</button></div>
        <section className="comm-history"><h3>Riwayat Komunikasi</h3>{data.history?.length ? data.history.map(item => <article key={item.id}><div><strong>{TEMPLATE_LABELS[item.event_type] || item.event_type}</strong><span>{formatDate(item.created_at)} · {item.operator || "System"}</span></div><p>{item.message}</p></article>) : <p className="comm-empty">Belum ada komunikasi yang dicatat untuk order ini.</p>}</section>
      </div>}
    </div>
  </div>;
}
