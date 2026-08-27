import { useEffect, useState } from "react";
import "./App.css";

function rupiah(value) {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(value || 0);
}

function App() {
  const [summary, setSummary] = useState(null);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadDashboard() {
      try {
        const [summaryResponse, ordersResponse] = await Promise.all([
          fetch("/api/summary/today"),
          fetch("/api/orders"),
        ]);

        if (!summaryResponse.ok) {
          throw new Error("Gagal mengambil summary");
        }

        if (!ordersResponse.ok) {
          throw new Error("Gagal mengambil order");
        }

        const summaryData = await summaryResponse.json();
        const ordersData = await ordersResponse.json();

        setSummary(summaryData);
        setOrders(Array.isArray(ordersData) ? ordersData : []);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, []);

  const activeLaundry =
    (summary?.status?.NEW || 0) +
    (summary?.status?.RECEIVED || 0) +
    (summary?.status?.WASHING || 0) +
    (summary?.status?.DRYING || 0) +
    (summary?.status?.IRONING || 0) +
    (summary?.status?.READY || 0) +
    (summary?.status?.DELIVERING || 0);

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">D</div>

          <div>
            <h2>Dayu Cleanset</h2>
            <span>Laundry Management</span>
          </div>
        </div>

        <nav className="menu">
          <button className="menu-item active">
            <span>▦</span>
            Dashboard
          </button>

          <button className="menu-item">
            <span>▤</span>
            Order
          </button>

          <button className="menu-item">
            <span>♙</span>
            Customer
          </button>

          <button className="menu-item">
            <span>◫</span>
            Service
          </button>

          <button className="menu-item">
            <span>Rp</span>
            Pembayaran
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="user-avatar">A</div>

          <div>
            <strong>Administrator</strong>
            <span>ADMIN</span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <h1>Dashboard</h1>
            <p>Ringkasan operasional Dayu Cleanset hari ini.</p>
          </div>

          <div className="today">
            {new Date().toLocaleDateString("id-ID", {
              weekday: "long",
              day: "2-digit",
              month: "long",
              year: "numeric",
            })}
          </div>
        </header>

        {loading ? (
          <div className="loading">Memuat dashboard...</div>
        ) : (
          <>
            <section className="summary-grid">
              <div className="summary-card">
                <div className="card-label">Total Order</div>
                <div className="card-value">
                  {summary?.total_orders || 0}
                </div>
                <div className="card-foot">Order hari ini</div>
              </div>

              <div className="summary-card">
                <div className="card-label">Laundry Aktif</div>
                <div className="card-value">{activeLaundry}</div>
                <div className="card-foot">
                  Masih dalam proses
                </div>
              </div>

              <div className="summary-card">
                <div className="card-label">Total Transaksi</div>
                <div className="card-value money">
                  {rupiah(summary?.total_amount)}
                </div>
                <div className="card-foot">
                  Nilai order hari ini
                </div>
              </div>

              <div className="summary-card">
                <div className="card-label">Belum Lunas</div>
                <div className="card-value">
                  {summary?.payment?.unpaid_orders || 0}
                </div>
                <div className="card-foot">
                  Order belum dibayar
                </div>
              </div>
            </section>

            <section className="content-card">
              <div className="section-header">
                <div>
                  <h2>Order Terbaru</h2>
                  <p>Daftar order laundry terbaru.</p>
                </div>

                <button className="primary-button">
                  + Order Baru
                </button>
              </div>

              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Order</th>
                      <th>Customer</th>
                      <th>Berat</th>
                      <th>Status Laundry</th>
                      <th>Pembayaran</th>
                      <th>Total</th>
                    </tr>
                  </thead>

                  <tbody>
                    {orders.slice(0, 8).map((order) => (
                      <tr key={order.order_number}>
                        <td>
                          <strong>{order.order_number}</strong>
                        </td>

                        <td>
                          {order.customer || "-"}
                        </td>

                        <td>
                          {order.total_weight || 0} KG
                        </td>

                        <td>
                          <span
                            className={`badge status-${(
                              order.status || ""
                            ).toLowerCase()}`}
                          >
                            {order.status}
                          </span>
                        </td>

                        <td>
                          <span
                            className={`badge payment-${(
                              order.payment_status || ""
                            ).toLowerCase()}`}
                          >
                            {order.payment_status}
                          </span>
                        </td>

                        <td>
                          <strong>{rupiah(order.total)}</strong>
                        </td>
                      </tr>
                    ))}

                    {orders.length === 0 && (
                      <tr>
                        <td colSpan="6" className="empty-state">
                          Belum ada order.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
