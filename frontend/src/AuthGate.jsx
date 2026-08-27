import { useEffect, useState } from "react";
import "./AuthGate.css";

function LoginScreen({ onLoggedIn }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Login gagal");
      onLoggedIn(data.user);
    } catch (loginError) {
      setError(loginError.message || "Login gagal");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="login-card" onSubmit={submit}>
        <div className="login-logo">D</div>
        <h1>Dayu Cleanset</h1>
        <p>Login ke Laundry Management</p>
        {error && <div className="auth-error">{error}</div>}
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
        </label>
        <button type="submit" disabled={loading}>{loading ? "Masuk..." : "Login"}</button>
      </form>
    </div>
  );
}

function UserManagement({ onClose }) {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", username: "", password: "", role: "STAFF" });

  async function loadUsers() {
    const response = await fetch("/api/admin/users");
    const data = await response.json();
    if (!response.ok) throw new Error(data?.detail || "Gagal mengambil user");
    setUsers(data);
  }

  useEffect(() => {
    loadUsers().catch((e) => setError(e.message));
  }, []);

  async function createUser(event) {
    event.preventDefault();
    setCreating(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch("/api/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Gagal membuat user");
      setForm({ name: "", username: "", password: "", role: "STAFF" });
      setMessage(`User ${data.name} berhasil dibuat.`);
      await loadUsers();
    } catch (e) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  }

  async function updateUser(user, changes) {
    setError("");
    setMessage("");
    try {
      const response = await fetch(`/api/admin/users/${user.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(changes),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Gagal memperbarui user");
      setMessage(`User ${data.name} diperbarui.`);
      await loadUsers();
    } catch (e) {
      setError(e.message);
    }
  }

  async function resetPassword(user) {
    const password = window.prompt(`Password baru untuk ${user.name} (minimal 8 karakter):`);
    if (!password) return;
    await updateUser(user, { password });
  }

  return (
    <div className="user-modal-backdrop" onMouseDown={onClose}>
      <div className="user-modal" onMouseDown={(e) => e.stopPropagation()}>
        <div className="user-modal-header">
          <div><h2>User Management</h2><p>Kelola akun dan role operasional.</p></div>
          <button type="button" onClick={onClose}>×</button>
        </div>
        <div className="user-modal-body">
          {error && <div className="auth-error">{error}</div>}
          {message && <div className="auth-success">{message}</div>}

          <form className="create-user-form" onSubmit={createUser}>
            <h3>Tambah User</h3>
            <input placeholder="Nama" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            <input placeholder="Username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
            <input type="password" placeholder="Password minimal 8 karakter" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="ADMIN">ADMIN</option>
              <option value="KASIR">KASIR</option>
              <option value="STAFF">STAFF</option>
            </select>
            <button type="submit" disabled={creating}>{creating ? "Menyimpan..." : "+ Tambah User"}</button>
          </form>

          <div className="user-list">
            <h3>Daftar User</h3>
            {users.map((user) => (
              <div className="user-row" key={user.id}>
                <div className="user-main"><strong>{user.name}</strong><span>@{user.username}</span></div>
                <select value={user.role} onChange={(e) => updateUser(user, { role: e.target.value })}>
                  <option value="ADMIN">ADMIN</option>
                  <option value="KASIR">KASIR</option>
                  <option value="STAFF">STAFF</option>
                </select>
                <label className="active-toggle">
                  <input type="checkbox" checked={user.is_active} onChange={(e) => updateUser(user, { is_active: e.target.checked })} /> Aktif
                </label>
                <button type="button" onClick={() => resetPassword(user)}>Reset Password</button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AuthGate({ children }) {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  const [manageUsers, setManageUsers] = useState(false);

  async function checkSession() {
    try {
      const response = await fetch("/api/auth/me");
      if (!response.ok) throw new Error("not logged in");
      const data = await response.json();
      window.dayuCurrentUser = data;
      setUser(data);
    } catch {
      window.dayuCurrentUser = null;
      setUser(null);
    } finally {
      setChecking(false);
    }
  }

  useEffect(() => {
    checkSession();
  }, []);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    window.dayuCurrentUser = null;
    setUser(null);
    setManageUsers(false);
  }

  function loggedIn(nextUser) {
    window.dayuCurrentUser = nextUser;
    setUser(nextUser);
  }

  useEffect(() => {
    if (!user) return;
    const syncSidebar = () => {
      const footer = document.querySelector(".sidebar-footer");
      const strong = footer?.querySelector("strong");
      const span = footer?.querySelector("div:last-child > span");
      if (strong) strong.textContent = user.name;
      if (span) span.textContent = user.role;
    };
    syncSidebar();
    const observer = new MutationObserver(syncSidebar);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [user]);

  if (checking) return <div className="auth-loading">Memeriksa session...</div>;
  if (!user) return <LoginScreen onLoggedIn={loggedIn} />;

  return (
    <>
      {children}
      <div className="session-toolbar">
        <div><strong>{user.name}</strong><span>{user.role}</span></div>
        {user.role === "ADMIN" && <button type="button" onClick={() => setManageUsers(true)}>User Management</button>}
        <button type="button" className="logout-button" onClick={logout}>Logout</button>
      </div>
      {manageUsers && <UserManagement onClose={() => setManageUsers(false)} />}
    </>
  );
}