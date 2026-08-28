import { useEffect, useMemo, useState } from "react";
import { OrderDetailTrigger } from "./OrderDetailModal.jsx";
import "./OperationsPages.css";

function rupiah(value) {
  return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(Number(value) || 0);
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("id-ID", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function CustomerPage() {
  const user = window.dayuCurrentUser;
  const canEdit = ["ADMIN", "KASIR"].includes(user?.role);
  const canDelete = user?.role === "ADMIN";
  const [customers, setCustomers] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(null);
  const [history, setHistory] = useState(null);
  const [newOpen, setNewOpen] = useState(false);
  const [form, setForm] = useState({ name: "", phone: "", address: "", notes: "" });

  async function load() {
    setLoading(true);
    try {
      const response = await fetch("/api/customers-list-v2");
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Gagal mengambil customer");
      setCustomers(data);
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return customers;
    return customers.filter((c) => `${c.name} ${c.phone} ${c.address || ""}`.toLowerCase().includes(q));
  }, [customers, query]);

  async function saveCustomer(event) {
    event.preventDefault(); setError("");
    const isEdit = Boolean(editing);
    const url = isEdit ? `/api/customers/${editing.id}` : "/api/customers";
    const response = await fetch(url, { method: isEdit ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
    const data = await response.json();
    if (!response.ok) { setError(data?.detail || "Gagal menyimpan customer"); return; }
    setEditing(null); setNewOpen(false); setForm({ name: "", phone: "", address: "", notes: "" }); await load();
  }

  function startEdit(customer) {
    setEditing(customer); setNewOpen(false);
    setForm({ name: customer.name || "", phone: customer.phone || "", address: customer.address || "", notes: customer.notes || "" });
  }

  async function showHistory(customer) {
    setError("");
    const response = await fetch(`/api/customers/${customer.id}/orders-v2`);
    const data = await response.json();
    if (!response.ok) { setError(data?.detail || "Gagal mengambil histori"); return; }
    setHistory(data);
  }

  async function deleteCustomer(customer) {
    if (!window.confirm(`Hapus customer ${customer.name}? Hanya customer tanpa histori order yang dapat dihapus.`)) return;
    const response = await fetch(`/api/customers/${customer.id}`, { method: "DELETE" });
    const data = await response.json();
    if (!response.ok) { setError(data?.detail || "Gagal menghapus customer"); return; }
    await load();
  }

  return <div className="workspace-page">
    <header className="workspace-header"><div><h1>Customer</h1><p>Data pelanggan dan histori order.</p></div>{canEdit && <button className="workspace-primary" onClick={() => { setNewOpen(true); setEditing(null); setForm({ name:"", phone:"", address:"", notes:"" }); }}>+ Customer Baru</button>}</header>
    <div className="workspace-stats"><div><span>Total Customer</span><strong>{customers.length}</strong></div><div><span>Total Order Customer</span><strong>{customers.reduce((s,c)=>s+Number(c.order_count||0),0)}</strong></div><div><span>Nilai Lifetime</span><strong>{rupiah(customers.reduce((s,c)=>s+Number(c.lifetime_value||0),0))}</strong></div></div>
    <section className="workspace-panel"><div className="workspace-search"><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Cari nama, WhatsApp / HP, alamat..." /></div>{error && <div className="workspace-error">{error}</div>}{loading ? <div className="workspace-loading">Memuat customer...</div> : <div className="responsive-table"><table><thead><tr><th>Customer</th><th>Order</th><th>Lifetime</th><th>Order Terakhir</th><th>Aksi</th></tr></thead><tbody>{filtered.map((c)=><tr key={c.id}><td><strong>{c.name}</strong><small>{c.phone}</small></td><td>{c.order_count}</td><td>{rupiah(c.lifetime_value)}</td><td>{formatDate(c.last_order_at)}</td><td><div className="row-actions"><button onClick={()=>showHistory(c)}>Histori</button>{canEdit&&<button onClick={()=>startEdit(c)}>Edit</button>}{canDelete&&<button className="danger" onClick={()=>deleteCustomer(c)}>Delete</button>}</div></td></tr>)}</tbody></table></div>}</section>
    {(newOpen || editing) && <div className="workspace-modal-backdrop" onMouseDown={()=>{setNewOpen(false);setEditing(null);}}><div className="workspace-modal" onMouseDown={(e)=>e.stopPropagation()}><div className="workspace-modal-header"><h2>{editing ? "Edit Customer" : "Customer Baru"}</h2><button onClick={()=>{setNewOpen(false);setEditing(null);}}>×</button></div><form onSubmit={saveCustomer}><label>Nama<input value={form.name} onChange={(e)=>setForm({...form,name:e.target.value})} required /></label><label>WhatsApp / HP<input value={form.phone} onChange={(e)=>setForm({...form,phone:e.target.value})} required /></label><label>Alamat / Keterangan Lokasi<input value={form.address} onChange={(e)=>setForm({...form,address:e.target.value})} /></label><label>Catatan<textarea rows="3" value={form.notes} onChange={(e)=>setForm({...form,notes:e.target.value})} /></label><div className="workspace-modal-actions"><button type="button" onClick={()=>{setNewOpen(false);setEditing(null);}}>Batal</button><button className="workspace-primary" type="submit">Simpan</button></div></form></div></div>}
    {history && <div className="workspace-modal-backdrop" onMouseDown={()=>setHistory(null)}><div className="workspace-modal wide" onMouseDown={(e)=>e.stopPropagation()}><div className="workspace-modal-header"><div><h2>{history.customer.name}</h2><p>{history.customer.phone}</p></div><button onClick={()=>setHistory(null)}>×</button></div><div className="responsive-table"><table><thead><tr><th>Order</th><th>Service</th><th>Status</th><th>Bayar</th><th>Total</th><th>Tanggal</th></tr></thead><tbody>{history.orders.map((o)=><tr key={o.order_number}><td><OrderDetailTrigger orderNumber={o.order_number}/></td><td>{o.service_speed}</td><td>{o.status}</td><td>{o.payment_status}</td><td>{rupiah(o.total)}</td><td>{formatDate(o.created_at)}</td></tr>)}</tbody></table></div></div></div>}
  </div>;
}

export function ServicePage() {
  const [config,setConfig]=useState(null); const [error,setError]=useState("");
  useEffect(()=>{fetch("/api/service-config-v2").then(async r=>{const d=await r.json(); if(!r.ok)throw new Error(d.detail); setConfig(d);}).catch(e=>setError(e.message));},[]);
  return <div className="workspace-page"><header className="workspace-header"><div><h1>Service</h1><p>Konfigurasi layanan aktif Dayu Cleanset.</p></div></header>{error&&<div className="workspace-error">{error}</div>}{config&&<><div className="service-grid"><article><span>Layanan</span><h2>NORMAL</h2><strong>{rupiah(config.normal.price_per_kg)} / KG</strong><p>{config.normal.sla}</p></article><article><span>Layanan</span><h2>EXPRESS</h2><strong>{rupiah(config.express.price_per_kg)} / KG</strong><p>{config.express.sla}</p></article><article><span>Promo</span><h2>{config.promo.percent}% OFF</h2><strong>Instagram + Google Maps</strong><p>{config.promo.description}</p></article></div><section className="workspace-panel info-panel"><h3>Aturan Harga</h3><p>Harga pada halaman ini adalah source of truth yang sama dengan kalkulasi Order Baru: NORMAL Rp30.000/KG, EXPRESS Rp55.000/KG, promo 5% jika dua syarat promo terpenuhi. Diskon nego tetap nominal manual per order.</p></section></>}</div>;
}

export function PaymentPage() {
  const [payments,setPayments]=useState([]); const [query,setQuery]=useState(""); const [method,setMethod]=useState("ALL"); const [loading,setLoading]=useState(true); const [error,setError]=useState("");
  async function load(){setLoading(true);try{const r=await fetch("/api/payments-list-v2");const d=await r.json();if(!r.ok)throw new Error(d.detail);setPayments(d);}catch(e){setError(e.message);}finally{setLoading(false);}}
  useEffect(()=>{load(); const refresh=()=>load(); window.addEventListener("dayu:orders-changed",refresh); return()=>window.removeEventListener("dayu:orders-changed",refresh);},[]);
  const filtered=useMemo(()=>{const q=query.toLowerCase().trim();return payments.filter(p=>(method==="ALL"||p.payment_method===method)&&(!q||`${p.order_number} ${p.customer} ${p.phone} ${p.operator||""}`.toLowerCase().includes(q)));},[payments,query,method]);
  const total=filtered.reduce((s,p)=>s+Number(p.amount||0),0);
  return <div className="workspace-page"><header className="workspace-header"><div><h1>Pembayaran</h1><p>Riwayat transaksi pembayaran laundry.</p></div></header><div className="workspace-stats"><div><span>Transaksi</span><strong>{filtered.length}</strong></div><div><span>Total Diterima</span><strong>{rupiah(total)}</strong></div></div><section className="workspace-panel"><div className="payment-filters"><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Cari order, customer, HP, operator..."/><select value={method} onChange={(e)=>setMethod(e.target.value)}><option value="ALL">Semua Metode</option><option>CASH</option><option>QRIS</option><option>TRANSFER</option></select></div>{error&&<div className="workspace-error">{error}</div>}{loading?<div className="workspace-loading">Memuat pembayaran...</div>:<div className="responsive-table"><table><thead><tr><th>Order</th><th>Customer</th><th>Metode</th><th>Jumlah</th><th>Operator</th><th>Waktu</th></tr></thead><tbody>{filtered.map(p=><tr key={p.id}><td><OrderDetailTrigger orderNumber={p.order_number}/></td><td><strong>{p.customer}</strong><small>{p.phone}</small></td><td><span className="method-pill">{p.payment_method}</span></td><td><strong>{rupiah(p.amount)}</strong></td><td>{p.operator||"System"}</td><td>{formatDate(p.paid_at)}</td></tr>)}</tbody></table></div>}</section></div>;
}
