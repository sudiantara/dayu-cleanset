import { useEffect, useMemo, useState } from "react";
import "./App.css";

function rupiah(value) {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(Number(value) || 0);
}

function createInitialOrderForm() {
  return {
    customer_id: "",
    hotel_name: "",
    room_number: "",
    location_notes: "",
    service_speed: "NORMAL",
    requested_finish_at: "",
    total_weight: "",
    instagram_followed: false,
    google_reviewed: false,
    special_discount: "",
    special_discount_reason: "",
    notes: "",
    payment_mode: "LATER",
    payment_method: "CASH",
  };
}

function createInitialCustomerForm() {
  return {
    name: "",
    phone: "",
  };
}

function App() {
  const [summary, setSummary] = useState(null);
  const [orders, setOrders] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [orderModalOpen, setOrderModalOpen] = useState(false);
  const [orderForm, setOrderForm] = useState(createInitialOrderForm());
  const [quickCustomerOpen, setQuickCustomerOpen] = useState(false);
  const [customerForm, setCustomerForm] = useState(createInitialCustomerForm());
  const [creatingCustomer, setCreatingCustomer] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");

  async function loadDashboard() {
    try {
      const [summaryResponse, ordersResponse, customersResponse] =
        await Promise.all([
          fetch("/api/summary/today"),
          fetch("/api/orders"),
          fetch("/api/customers"),
        ]);

      if (!summaryResponse.ok) {
        throw new Error("Gagal mengambil summary");
      }

      if (!ordersResponse.ok) {
        throw new Error("Gagal mengambil order");
      }

      if (!customersResponse.ok) {
        throw new Error("Gagal mengambil customer");
      }

      const summaryData = await summaryResponse.json();
      const ordersData = await ordersResponse.json();
      const customersData = await customersResponse.json();

      setSummary(summaryData);
      setOrders(Array.isArray(ordersData) ? ordersData : []);
      setCustomers(Array.isArray(customersData) ? customersData : []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
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

  const calculation = useMemo(() => {
    const weight = Number(orderForm.total_weight) || 0;
    const pricePerKg = orderForm.service_speed === "EXPRESS" ? 55000 : 30000;
    const subtotal = weight * pricePerKg;
    const promoEligible =
      orderForm.instagram_followed && orderForm.google_reviewed;
    const promoDiscount = promoEligible ? subtotal * 0.05 : 0;
    const specialDiscount = Math.max(
      Number(orderForm.special_discount) || 0,
      0,
    );
    const discount = promoDiscount + specialDiscount;
    const total = Math.max(subtotal - discount, 0);

    return {
      pricePerKg,
      subtotal,
      promoDiscount,
      specialDiscount,
      discount,
      total,
    };
  }, [orderForm]);

  function updateOrderForm(field, value) {
    setOrderForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function updateCustomerForm(field, value) {
    setCustomerForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function openOrderModal() {
    setOrderForm(createInitialOrderForm());
    setCustomerForm(createInitialCustomerForm());
    setQuickCustomerOpen(false);
    setFormError("");
    setFormSuccess("");
    setOrderModalOpen(true);
  }

  function closeOrderModal() {
    if (submitting || creatingCustomer) return;
    setOrderModalOpen(false);
  }

  async function createQuickCustomer() {
    setFormError("");
    setFormSuccess("");

    const name = customerForm.name.trim();
    const phone = customerForm.phone.trim();

    if (!name) {
      setFormError("Nama customer wajib diisi.");
      return;
    }

    if (!phone) {
      setFormError("Nomor WhatsApp / HP wajib diisi.");
      return;
    }

    setCreatingCustomer(true);

    try {
      const response = await fetch("/api/customers", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name,
          phone,
          address: null,
          notes: "Dibuat dari Quick Customer pada Order Baru",
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.detail || "Gagal membuat customer.");
      }

      const newCustomer = data.customer;

      setCustomers((current) => [...current, newCustomer]);
      updateOrderForm("customer_id", String(newCustomer.id));
      setCustomerForm(createInitialCustomerForm());
      setQuickCustomerOpen(false);
      setFormSuccess(`Customer ${newCustomer.name} berhasil dibuat dan dipilih.`);
    } catch (error) {
      setFormError(error.message || "Terjadi kesalahan saat membuat customer.");
    } finally {
      setCreatingCustomer(false);
    }
  }

  async function submitOrder(event) {
    event.preventDefault();
    setFormError("");
    setFormSuccess("");

    const customerId = Number(orderForm.customer_id);
    const totalWeight = Number(orderForm.total_weight);
    const specialDiscount = Number(orderForm.special_discount) || 0;

    if (!customerId) {
      setFormError("Pilih customer terlebih dahulu.");
      return;
    }

    if (!orderForm.hotel_name.trim()) {
      setFormError("Hotel / Villa wajib diisi.");
      return;
    }

    if (!totalWeight || totalWeight <= 0) {
      setFormError("Berat laundry harus lebih dari 0 KG.");
      return;
    }

    if (!orderForm.requested_finish_at) {
      setFormError("Target selesai wajib diisi.");
      return;
    }

    if (calculation.discount > calculation.subtotal) {
      setFormError("Total diskon tidak boleh melebihi subtotal.");
      return;
    }

    if (specialDiscount > 0 && !orderForm.special_discount_reason.trim()) {
      setFormError("Isi alasan jika menggunakan diskon nego.");
      return;
    }

    setSubmitting(true);

    try {
      const payload = {
        customer_id: customerId,
        hotel_name: orderForm.hotel_name.trim(),
        room_number: orderForm.room_number.trim() || null,
        location_notes: orderForm.location_notes.trim() || null,
        service_speed: orderForm.service_speed,
        requested_finish_at: new Date(
          orderForm.requested_finish_at,
        ).toISOString(),
        total_weight: totalWeight,
        instagram_followed: orderForm.instagram_followed,
        google_reviewed: orderForm.google_reviewed,
        special_discount: specialDiscount,
        special_discount_reason:
          orderForm.special_discount_reason.trim() || null,
        pickup_type: "CUSTOMER_DROP",
        notes: orderForm.notes.trim() || null,
        created_by: 1,
      };

      const createResponse = await fetch("/api/orders", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const createData = await createResponse.json();

      if (!createResponse.ok) {
        throw new Error(createData?.detail || "Gagal membuat order.");
      }

      const orderNumber = createData.order.order_number;

      if (orderForm.payment_mode === "NOW") {
        const paymentResponse = await fetch(
          `/api/orders/${orderNumber}/mark-paid`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              payment_method: orderForm.payment_method,
              reference_number: null,
              notes: "Pembayaran saat order dibuat",
              created_by: 1,
            }),
          },
        );

        const paymentData = await paymentResponse.json();

        if (!paymentResponse.ok) {
          throw new Error(
            `Order ${orderNumber} berhasil dibuat, tetapi pembayaran gagal: ${
              paymentData?.detail || "unknown error"
            }`,
          );
        }
      }

      setFormSuccess(`Order ${orderNumber} berhasil dibuat.`);
      await loadDashboard();

      window.setTimeout(() => {
        setOrderModalOpen(false);
        setFormSuccess("");
      }, 900);
    } catch (error) {
      setFormError(error.message || "Terjadi kesalahan saat membuat order.");
    } finally {
      setSubmitting(false);
    }
  }

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
                <div className="card-value">{summary?.total_orders || 0}</div>
                <div className="card-foot">Order hari ini</div>
              </div>

              <div className="summary-card">
                <div className="card-label">Laundry Aktif</div>
                <div className="card-value">{activeLaundry}</div>
                <div className="card-foot">Masih dalam proses</div>
              </div>

              <div className="summary-card">
                <div className="card-label">Total Transaksi</div>
                <div className="card-value money">
                  {rupiah(summary?.total_amount)}
                </div>
                <div className="card-foot">Nilai order hari ini</div>
              </div>

              <div className="summary-card">
                <div className="card-label">Belum Lunas</div>
                <div className="card-value">
                  {summary?.payment?.unpaid_orders || 0}
                </div>
                <div className="card-foot">Order belum dibayar</div>
              </div>
            </section>

            <section className="content-card">
              <div className="section-header">
                <div>
                  <h2>Order Terbaru</h2>
                  <p>Daftar order laundry terbaru.</p>
                </div>

                <button className="primary-button" onClick={openOrderModal}>
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
                        <td>{order.customer || "-"}</td>
                        <td>{order.total_weight || 0} KG</td>
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

      {orderModalOpen && (
        <div className="modal-backdrop" onMouseDown={closeOrderModal}>
          <div
            className="order-modal"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h2>Order Baru</h2>
                <p>Input laundry customer hotel / villa.</p>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={closeOrderModal}
                disabled={submitting || creatingCustomer}
              >
                ×
              </button>
            </div>

            <form onSubmit={submitOrder}>
              <div className="modal-body">
                {formError && <div className="form-alert error">{formError}</div>}
                {formSuccess && (
                  <div className="form-alert success">{formSuccess}</div>
                )}

                <section className="form-section">
                  <div className="form-section-title">Customer</div>
                  <div className="form-grid two-column">
                    <label className="field field-full">
                      <span>Customer *</span>
                      <select
                        value={orderForm.customer_id}
                        onChange={(event) =>
                          updateOrderForm("customer_id", event.target.value)
                        }
                        required
                      >
                        <option value="">Pilih customer</option>
                        {customers.map((customer) => (
                          <option key={customer.id} value={customer.id}>
                            {customer.name} — {customer.phone}
                          </option>
                        ))}
                      </select>
                    </label>

                    <div className="field field-full">
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => {
                          setFormError("");
                          setFormSuccess("");
                          setQuickCustomerOpen((current) => !current);
                        }}
                        disabled={creatingCustomer}
                      >
                        {quickCustomerOpen ? "Tutup Customer Baru" : "+ Customer Baru"}
                      </button>
                    </div>

                    {quickCustomerOpen && (
                      <>
                        <label className="field">
                          <span>Nama Customer *</span>
                          <input
                            value={customerForm.name}
                            onChange={(event) =>
                              updateCustomerForm("name", event.target.value)
                            }
                            placeholder="Contoh: John Smith"
                          />
                        </label>

                        <label className="field">
                          <span>WhatsApp / No. HP *</span>
                          <input
                            value={customerForm.phone}
                            onChange={(event) =>
                              updateCustomerForm("phone", event.target.value)
                            }
                            placeholder="Contoh: +61412345678"
                          />
                        </label>

                        <div className="field field-full">
                          <button
                            type="button"
                            className="primary-button"
                            onClick={createQuickCustomer}
                            disabled={creatingCustomer}
                          >
                            {creatingCustomer
                              ? "Menyimpan Customer..."
                              : "Simpan & Pilih Customer"}
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                </section>

                <section className="form-section">
                  <div className="form-section-title">Lokasi Menginap</div>
                  <div className="form-grid two-column">
                    <label className="field">
                      <span>Hotel / Villa *</span>
                      <input
                        value={orderForm.hotel_name}
                        onChange={(event) =>
                          updateOrderForm("hotel_name", event.target.value)
                        }
                        placeholder="Contoh: Grand Bali Hotel"
                        required
                      />
                    </label>

                    <label className="field">
                      <span>Room</span>
                      <input
                        value={orderForm.room_number}
                        onChange={(event) =>
                          updateOrderForm("room_number", event.target.value)
                        }
                        placeholder="305"
                      />
                    </label>

                    <label className="field field-full">
                      <span>Catatan Lokasi</span>
                      <input
                        value={orderForm.location_notes}
                        onChange={(event) =>
                          updateOrderForm("location_notes", event.target.value)
                        }
                        placeholder="Contoh: Titip / ambil di reception"
                      />
                    </label>
                  </div>
                </section>

                <section className="form-section">
                  <div className="form-section-title">Layanan Laundry</div>

                  <div className="speed-options">
                    <label
                      className={`speed-card ${
                        orderForm.service_speed === "NORMAL" ? "selected" : ""
                      }`}
                    >
                      <input
                        type="radio"
                        name="service_speed"
                        value="NORMAL"
                        checked={orderForm.service_speed === "NORMAL"}
                        onChange={() => updateOrderForm("service_speed", "NORMAL")}
                      />
                      <strong>NORMAL</strong>
                      <span>Rp30.000 / KG</span>
                      <small>Selesai maksimal 1 hari</small>
                    </label>

                    <label
                      className={`speed-card ${
                        orderForm.service_speed === "EXPRESS" ? "selected" : ""
                      }`}
                    >
                      <input
                        type="radio"
                        name="service_speed"
                        value="EXPRESS"
                        checked={orderForm.service_speed === "EXPRESS"}
                        onChange={() => updateOrderForm("service_speed", "EXPRESS")}
                      />
                      <strong>EXPRESS</strong>
                      <span>Rp55.000 / KG</span>
                      <small>Target selesai di bawah 6 jam</small>
                    </label>
                  </div>

                  <div className="form-grid two-column form-gap-top">
                    <label className="field">
                      <span>Berat Laundry (KG) *</span>
                      <input
                        type="number"
                        min="0.1"
                        step="0.1"
                        value={orderForm.total_weight}
                        onChange={(event) =>
                          updateOrderForm("total_weight", event.target.value)
                        }
                        placeholder="4"
                        required
                      />
                    </label>

                    <label className="field">
                      <span>Target Selesai *</span>
                      <input
                        type="datetime-local"
                        value={orderForm.requested_finish_at}
                        onChange={(event) =>
                          updateOrderForm(
                            "requested_finish_at",
                            event.target.value,
                          )
                        }
                        required
                      />
                    </label>

                    <label className="field field-full">
                      <span>Catatan Laundry</span>
                      <textarea
                        rows="2"
                        value={orderForm.notes}
                        onChange={(event) =>
                          updateOrderForm("notes", event.target.value)
                        }
                        placeholder="Contoh: Baju putih dipisah"
                      />
                    </label>
                  </div>
                </section>

                <section className="form-section">
                  <div className="form-section-title">Promo & Diskon</div>

                  <div className="check-grid">
                    <label className="check-card">
                      <input
                        type="checkbox"
                        checked={orderForm.instagram_followed}
                        onChange={(event) =>
                          updateOrderForm(
                            "instagram_followed",
                            event.target.checked,
                          )
                        }
                      />
                      <div>
                        <strong>Follow Instagram</strong>
                        <span>Salah satu syarat promo 5%</span>
                      </div>
                    </label>

                    <label className="check-card">
                      <input
                        type="checkbox"
                        checked={orderForm.google_reviewed}
                        onChange={(event) =>
                          updateOrderForm(
                            "google_reviewed",
                            event.target.checked,
                          )
                        }
                      />
                      <div>
                        <strong>Review Google Maps</strong>
                        <span>Salah satu syarat promo 5%</span>
                      </div>
                    </label>
                  </div>

                  <div className="form-grid two-column form-gap-top">
                    <label className="field">
                      <span>Diskon Nego (Rp)</span>
                      <input
                        type="number"
                        min="0"
                        step="1000"
                        value={orderForm.special_discount}
                        onChange={(event) =>
                          updateOrderForm("special_discount", event.target.value)
                        }
                        placeholder="0"
                      />
                    </label>

                    <label className="field">
                      <span>Alasan Nego</span>
                      <input
                        value={orderForm.special_discount_reason}
                        onChange={(event) =>
                          updateOrderForm(
                            "special_discount_reason",
                            event.target.value,
                          )
                        }
                        placeholder="Contoh: Customer nego"
                      />
                    </label>
                  </div>
                </section>

                <section className="form-section">
                  <div className="form-section-title">Pembayaran</div>

                  <div className="payment-choice">
                    <label>
                      <input
                        type="radio"
                        name="payment_mode"
                        checked={orderForm.payment_mode === "LATER"}
                        onChange={() => updateOrderForm("payment_mode", "LATER")}
                      />
                      Bayar Nanti
                    </label>
                    <label>
                      <input
                        type="radio"
                        name="payment_mode"
                        checked={orderForm.payment_mode === "NOW"}
                        onChange={() => updateOrderForm("payment_mode", "NOW")}
                      />
                      Bayar Sekarang
                    </label>
                  </div>

                  {orderForm.payment_mode === "NOW" && (
                    <label className="field payment-method-field">
                      <span>Metode Pembayaran</span>
                      <select
                        value={orderForm.payment_method}
                        onChange={(event) =>
                          updateOrderForm("payment_method", event.target.value)
                        }
                      >
                        <option value="CASH">CASH</option>
                        <option value="QRIS">QRIS</option>
                        <option value="TRANSFER">TRANSFER</option>
                      </select>
                    </label>
                  )}
                </section>

                <section className="price-summary">
                  <div>
                    <span>
                      {orderForm.service_speed} · {rupiah(calculation.pricePerKg)} / KG
                    </span>
                    <strong>{rupiah(calculation.subtotal)}</strong>
                  </div>
                  <div>
                    <span>Promo Instagram + Google 5%</span>
                    <strong>- {rupiah(calculation.promoDiscount)}</strong>
                  </div>
                  <div>
                    <span>Diskon Nego</span>
                    <strong>- {rupiah(calculation.specialDiscount)}</strong>
                  </div>
                  <div className="price-total">
                    <span>TOTAL</span>
                    <strong>{rupiah(calculation.total)}</strong>
                  </div>
                </section>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={closeOrderModal}
                  disabled={submitting || creatingCustomer}
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="primary-button"
                  disabled={submitting || creatingCustomer}
                >
                  {submitting ? "Menyimpan..." : "Simpan Order"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
