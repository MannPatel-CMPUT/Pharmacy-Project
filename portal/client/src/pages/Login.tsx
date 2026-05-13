import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

export default function Login() {
  const [params] = useSearchParams();
  const next = params.get("next") || "/workspace";
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg =
          typeof data.detail === "string"
            ? data.detail
            : typeof data.error === "string"
              ? data.error
              : "Login failed.";
        setError(msg);
        return;
      }
      window.location.href = next.startsWith("/") ? next : "/workspace";
    } catch {
      setError("Network error — is the API running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="glass-card">
        <h1>Welcome back</h1>
        <p className="sub">Sign in to open the Pharma Checker workspace.</p>
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              name="username"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error ? <div className="err">{error}</div> : null}
          <button className="btn-primary" type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <div className="footer-links" style={{ marginTop: 10 }}>
          <Link to="/forgot-password">Forgot password?</Link>
        </div>
        <div className="footer-links">
          New here? <Link to="/signup">Create an account</Link>
        </div>
      </div>
    </div>
  );
}
