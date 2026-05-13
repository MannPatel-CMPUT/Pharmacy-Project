import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");
    setLoading(true);
    try {
      const res = await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(typeof data.detail === "string" ? data.detail : "Request failed.");
        return;
      }
      setMessage(data.message || "Check your email for next steps.");
      if (data.reset_url) {
        setMessage(`${data.message || "If an account exists…"} In this demo, open: ${data.reset_url}`);
      }
    } catch {
      setError("Network error.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="glass-card">
        <h1>Reset password</h1>
        <p className="sub">Enter the email on your account. We&apos;ll give you a one-time reset link (demo — no email is sent).</p>
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="fp-email">Email</label>
            <input
              id="fp-email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          {error ? <div className="err">{error}</div> : null}
          {message ? <div className="muted" style={{ marginBottom: 12, fontSize: "0.88rem", lineHeight: 1.5 }}>{message}</div> : null}
          <button className="btn-primary" type="submit" disabled={loading}>
            {loading ? "Sending…" : "Request reset link"}
          </button>
        </form>
        <div className="footer-links">
          <Link to="/login">Back to sign in</Link>
        </div>
      </div>
    </div>
  );
}
