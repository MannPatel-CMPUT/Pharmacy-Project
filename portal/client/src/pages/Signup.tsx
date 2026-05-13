import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

export default function Signup() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, email, phone, password }),
      });
      const raw = await res.text();
      let data: Record<string, unknown> = {};
      try {
        data = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
      } catch {
        data = {};
      }
      if (!res.ok) {
        let msg = "Could not sign up.";
        if (typeof data.detail === "string") msg = data.detail;
        else if (Array.isArray(data.detail))
          msg =
            data.detail
              .map((d: { msg?: string; message?: string }) => d.msg || d.message || "")
              .filter(Boolean)
              .join("; ") || msg;
        else if (typeof data.error === "string") msg = data.error;
        else if (raw && !Object.keys(data).length) msg = `${res.status}: ${raw.slice(0, 200)}`;
        setError(msg);
        return;
      }
      window.location.href = "/workspace";
    } catch {
      setError("Network error — is the API running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="glass-card" style={{ maxWidth: 440 }}>
        <h1>Create your account</h1>
        <p className="sub">Educational prototype — use a strong password you do not reuse elsewhere.</p>
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="su-user">Username</label>
            <input
              id="su-user"
              name="username"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={2}
            />
          </div>
          <div className="field">
            <label htmlFor="su-email">Email</label>
            <input
              id="su-email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="su-phone">Phone</label>
            <input
              id="su-phone"
              name="phone"
              type="tel"
              autoComplete="tel"
              placeholder="e.g. (555) 123-4567"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="su-pass">Password</label>
            <input
              id="su-pass"
              name="password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </div>
          {error ? <div className="err">{error}</div> : null}
          <button className="btn-primary" type="submit" disabled={loading}>
            {loading ? "Creating account…" : "Sign up and continue"}
          </button>
        </form>
        <div className="footer-links">
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
