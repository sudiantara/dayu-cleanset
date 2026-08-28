import { useEffect, useMemo, useState } from "react";
import { OrderDetailTrigger } from "./OrderDetailModal.jsx";
import "./OrderListPage.css";

function rupiah(value) {
  return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(Number(value) || 0);
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("id-ID", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

const STATUS_OPTIONS = ["ALL", "NEW", "RECEIVED", "WASHING", "DRYING", "IRONING", "READY", "DELIVERING", "COMPLETE", "PICKED_UP", "CANCELLED"];

export default function OrderListPage({ onNewOrder }) {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ALL");
  const [payment, setPayment] = useState("ALL");
  const [speed, setSpeed] = useState("ALL");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 10;

  async function loadOrders({ silent = false } = {}) {
    if (!silent) setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/orders-list-v2");
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Gagal mengambil order");
      setOrders(Array.isArray(data) ? data : []);
    } catch (loadError) {
      setError(loadError.message || "Gagal mengambil order");
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => { loadOrders(); }, []);

  useEffect(() => {
    const refresh = () => loadOrders({ silent: true });
    window.addEventListener("dayu:orders-changed", refresh);
    return () => window.removeEventListener("dayu:orders-changed", refresh);
  }, []);

  useEffect(() => { setPage(1); }, [query, status, payment, speed, dateFrom, dateTo]);

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return orders.filter((order) => {
      const haystack = [order.order_number, order.customer, order.phone, order.hotel_name, order.room_number].filter(Boolean).join(" ").toLowerCase();
      if (normalizedQuery && !haystack.includes(normalizedQuery)) return false;
      if (status !== "ALL" && order.status !== status) return false;
      if (payment !== "ALL" && order.payment_status !== payment) return false;
      if (speed !== "ALL" && order.service_speed !== speed) return false;
      if (dateFrom || dateTo) {
        const created = order.created_at ? new Date(order.created_at) : null;
        if (!created || Number.isNaN(created.getTime())) return false;
        if (dateFrom && created < new Date(`${dateFrom}T00:00:00`)) return false;
        if (dateTo && created > new Date(`${dateTo}T23:59:59`)) return false;
      }
      return true;
    });
  }, [orders, query, status, payment, speed, dateFrom, dateTo]);

  const totals = useMemo(() => {
    const totalValue = filtered.reduce((sum, order) => sum + Number(order.total || 0), 0);
    const active = filtered.filter((order) => !["COMPLETE", "PICKED_UP", "CANCELLED"].includes(order.status)).length;
    const unpaid = filtered.filter((order) => order.payment_status !== "PAID").length;
    return { totalValue, active, unpaid };
  }, [filtered]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageRows = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  function resetFilters() {
    setQuery(""); setStatus("ALL"); setPayment("ALL"); setSpeed("ALL"); setDateFrom(""); setDateTo("");
  }

  return (
    <div className="order-list-page">
      <header className="order-page-header">
        <div><h1>Order</h1><p>Kelola dan cari seluruh order laundry.</p></div>
        <button className="order-new-button" type="button" onClick={onNewOrder}>+ Order Baru</button>
      </header>

      <section className="order-stats">
        <div><span>Total hasil</span><strong>{filtered.length}</strong></div>
        <div><span>Laundry aktif</span><strong>{totals.active}</strong></div>
        <div><span>Belum lunas</span><strong>{totals.unpaid}</strong></div>
        <div><span>Nilai order</span><strong>{rupiah(totals.totalValue)}</strong></div>
      </section>

      <section className="order-panel">
        <div className="order-filter-grid">
          <label className="order-search-field"><span>Cari</span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="No. order, customer, HP, hotel, room..." /></label>
          <label><span>Status Laundry</span><select value={status} onChange={(e) => setStatus(e.target.value)}>{STATUS_OPTIONS.map((item) => <option key={item} value={item}>{item === "ALL" ? "Semua Status" : item}</option>)}</select></label>
          <label><span>Pembayaran</span><select value={payment} onChange={(e) => setPayment(e.target.value)}><option value="ALL">Semua Pembayaran</option><option value="UNPAID">UNPAID</option><option value="PARTIAL">PARTIAL</option><option value="PAID">PAID</option></select></label>
          <label><span>Service</span><select value={speed} onChange={(e) => setSpeed(e.target.value)}><option value="ALL">Semua Service</option><option value="NORMAL">NORMAL</option><option value="EXPRESS">EXPRESS</option></select></label>
          <label><span>Dari Tanggal</span><input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /></label>
          <label><span>Sampai Tanggal</span><input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /></label>
          <button type="button" className="order-reset-button" onClick={resetFilters}>Reset Filter</button>
        </div>

        {error && <div className="order-error">{error}</div>}
        {loading ? <div className="order-loading">Memuat semua order...</div> : <>
          <div className="order-table-wrap"><table className="order-full-table">
            <thead><tr><th>Order</th><th>Customer</th><th>Service</th><th>Berat</th><th>Status</th><th>Pembayaran</th><th>Total</th><th>Dibuat</th></tr></thead>
            <tbody>
              {pageRows.map((order) => <tr key={order.order_number}>
                <td><OrderDetailTrigger orderNumber={order.order_number} onChanged={() => loadOrders({ silent: true })} /></td>
                <td><strong>{order.customer || "-"}</strong><small>{order.phone || ""}</small></td>
                <td>{order.service_speed || "-"}</td><td>{Number(order.total_weight || 0)} KG</td>
                <td><span className={`order-pill status-${String(order.status || "").toLowerCase()}`}>{order.status}</span></td>
                <td><span className={`order-pill payment-${String(order.payment_status || "").toLowerCase()}`}>{order.payment_status}</span></td>
                <td><strong>{rupiah(order.total)}</strong></td><td>{formatDate(order.created_at)}</td>
              </tr>)}
              {pageRows.length === 0 && <tr><td colSpan="8" className="order-empty">Tidak ada order yang cocok dengan filter.</td></tr>}
            </tbody>
          </table></div>
          <div className="order-pagination"><span>Menampilkan {filtered.length === 0 ? 0 : (currentPage - 1) * pageSize + 1} - {Math.min(currentPage * pageSize, filtered.length)} dari {filtered.length} order</span><div>
            <button type="button" disabled={currentPage <= 1} onClick={() => setPage((v) => Math.max(1, v - 1))}>← Sebelumnya</button><strong>{currentPage} / {totalPages}</strong><button type="button" disabled={currentPage >= totalPages} onClick={() => setPage((v) => Math.min(totalPages, v + 1))}>Berikutnya →</button>
          </div></div>
        </>}
      </section>
    </div>
  );
}
