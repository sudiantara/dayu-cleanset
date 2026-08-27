import { useEffect, useState } from "react";
import "./OrderDetailModal.css";

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

export function OrderDetailTrigger({ orderNumber }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        className="order-link"
        onClick={() => setOpen(true)}
      >
        {orderNumber}
      </button>

      {open && (
        <OrderDetailModal
          orderNumber={orderNumber}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}

function OrderDetailModal({ orderNumber, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadDetail() {
      try {
        const response = await fetch(
          `/api/orders/${encodeURIComponent(orderNumber)}/overview-v2`,
        );
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data?.detail || "Gagal mengambil detail order.");
        }

        if (active) setDetail(data);
      } catch (loadError) {
        if (active) {
          setError(loadError.message || "Gagal mengambil detail order.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    loadDetail();

    return () => {
      active = false;
    };
  }, [orderNumber]);

  return (
    <div className="detail-backdrop" onMouseDown={onClose}>
      <div
        className="detail-modal"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="detail-header">
          <div>
            <span className="detail-kicker">DETAIL ORDER</span>
            <h2>{orderNumber}</h2>
          </div>
          <button type="button" className="detail-close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="detail-body">
          {loading && <div className="detail-message">Memuat detail order...</div>}
          {error && <div className="detail-message error">{error}</div>}

          {detail && (
            <>
              <div className="detail-status-row">
                <span className={`detail-badge status-${detail.service.status.toLowerCase()}`}>
                  {detail.service.status}
                </span>
                <span className={`detail-badge payment-${detail.billing.payment_status.toLowerCase()}`}>
                  {detail.billing.payment_status}
                </span>
                <span className="detail-created">
                  Dibuat {formatDate(detail.created_at)}
                </span>
              </div>

              <div className="detail-grid">
                <section className="detail-card">
                  <h3>Customer</h3>
                  <dl>
                    <div><dt>Nama</dt><dd>{detail.customer.name}</dd></div>
                    <div><dt>WhatsApp / HP</dt><dd>{detail.customer.phone}</dd></div>
                  </dl>
                </section>

                <section className="detail-card">
                  <h3>Lokasi Menginap</h3>
                  <dl>
                    <div><dt>Hotel / Villa</dt><dd>{detail.location.hotel_name || "-"}</dd></div>
                    <div><dt>Room</dt><dd>{detail.location.room_number || "-"}</dd></div>
                    <div><dt>Catatan</dt><dd>{detail.location.location_notes || "-"}</dd></div>
                  </dl>
                </section>

                <section className="detail-card">
                  <h3>Laundry</h3>
                  <dl>
                    <div><dt>Service</dt><dd>{detail.service.speed}</dd></div>
                    <div><dt>Berat</dt><dd>{detail.service.total_weight} KG</dd></div>
                    <div><dt>Target Selesai</dt><dd>{formatDate(detail.service.requested_finish_at)}</dd></div>
                    <div><dt>Catatan Laundry</dt><dd>{detail.notes || "-"}</dd></div>
                  </dl>
                </section>

                <section className="detail-card">
                  <h3>Promo</h3>
                  <dl>
                    <div><dt>Follow Instagram</dt><dd>{detail.promo.instagram_followed ? "YES" : "NO"}</dd></div>
                    <div><dt>Google Review</dt><dd>{detail.promo.google_reviewed ? "YES" : "NO"}</dd></div>
                    <div><dt>Promo 5%</dt><dd>- {rupiah(detail.promo.promo_discount)}</dd></div>
                    <div><dt>Diskon Nego</dt><dd>- {rupiah(detail.promo.special_discount)}</dd></div>
                    <div><dt>Alasan Nego</dt><dd>{detail.promo.special_discount_reason || "-"}</dd></div>
                  </dl>
                </section>
              </div>

              <section className="detail-billing">
                <h3>Rincian Pembayaran</h3>
                <div className="billing-line"><span>Subtotal</span><strong>{rupiah(detail.billing.subtotal)}</strong></div>
                <div className="billing-line discount"><span>Promo 5%</span><strong>- {rupiah(detail.promo.promo_discount)}</strong></div>
                <div className="billing-line discount"><span>Diskon Nego</span><strong>- {rupiah(detail.promo.special_discount)}</strong></div>
                <div className="billing-line total-discount"><span>Total Diskon</span><strong>- {rupiah(detail.billing.discount)}</strong></div>
                <div className="billing-line grand-total"><span>Total</span><strong>{rupiah(detail.billing.total)}</strong></div>
                <div className="billing-line"><span>Sudah Dibayar</span><strong>{rupiah(detail.billing.paid_amount)}</strong></div>
                <div className="billing-line remaining"><span>Sisa</span><strong>{rupiah(detail.billing.remaining_amount)}</strong></div>
              </section>

              <div className="detail-grid lower-grid">
                <section className="detail-card">
                  <h3>Riwayat Status</h3>
                  {detail.history.length === 0 ? (
                    <p className="detail-empty">Belum ada riwayat.</p>
                  ) : (
                    <div className="detail-timeline">
                      {detail.history.map((item) => (
                        <div className="timeline-item" key={item.id}>
                          <div className="timeline-dot" />
                          <div>
                            <strong>{item.status}</strong>
                            <p>{item.note || "-"}</p>
                            <small>{formatDate(item.created_at)} · {item.operator || "System"}</small>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </section>

                <section className="detail-card">
                  <h3>Riwayat Pembayaran</h3>
                  {detail.payments.length === 0 ? (
                    <p className="detail-empty">Belum ada pembayaran.</p>
                  ) : (
                    <div className="payment-list">
                      {detail.payments.map((payment) => (
                        <div className="payment-item" key={payment.id}>
                          <div>
                            <strong>{payment.payment_method}</strong>
                            <small>{formatDate(payment.created_at)}</small>
                          </div>
                          <strong>{rupiah(payment.amount)}</strong>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
