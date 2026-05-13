import { FormEvent, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = useMemo(() => params.get("token") || "", [params]);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!token) {
      setError("Missing token. Open the link from your reset request.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(typeof data.detail === "string" ? data.detail : "Reset failed.");
        return;
      }
      setDone(true);
    } catch {
      setError("Network error.");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="auth-shell">
        <div className="glass-card">
          <h1>Invalid link</h1>
          <p className="sub">This page needs a <code>?token=…</code> from your reset request.</p>
          <div className="footer-links">
            <Link to="/forgot-password">Request a new link</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-shell">
      <div className="glass-card">
        <h1>Choose a new password</h1>
        {done ? (
          <>
            <p className="sub">Your password was updated. You can sign in now.</p>
            <Link className="btn-primary" to="/login" style={{ display: "inline-block", textAlign: "center", textDecoration: "none" }}>
              Sign in
            </Link>
          </>
        ) : (
          <form onSubmit={onSubmit}>
            <div className="field">
              <label htmlFor="rp-pass">New password</label>
              <input
                id="rp-pass"
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
              {loading ? "Saving…" : "Update password"}
            </button>
          </form>
        )}
        <div className="footer-links">
          <Link to="/login">Back to sign in</Link>
        </div>
      </div>
    </div>
  );
}
