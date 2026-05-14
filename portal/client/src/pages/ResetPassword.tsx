import { FormEvent, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertCircle, ArrowRight, CheckCircle2, Eye, EyeOff, Loader2, Lock } from "lucide-react";
import { BrandRow } from "../components/BrandRow";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = useMemo(() => params.get("token") || "", [params]);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
      setError("Network error — please retry in a moment.");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="auth-shell" data-testid="reset-page-invalid">
        <div className="grid-scaffold" aria-hidden />
        <div className="auth-wrap">
          <BrandRow envLabel="Reset link invalid" />
          <div className="glass-card">
            <h1>Invalid link</h1>
            <p className="sub">
              This page needs a <code>?token=…</code> from your reset request.
            </p>
            <div className="footer-links">
              <Link to="/forgot-password" data-testid="reset-request-new-link">
                Request a new link
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-shell" data-testid="reset-page">
      <div className="grid-scaffold" aria-hidden />
      <div className="auth-wrap">
        <BrandRow envLabel="Choose new password" />
        <div className="glass-card">
          <h1>Choose a new password</h1>
          {done ? (
            <>
              <div className="notice" data-testid="reset-success">
                <CheckCircle2 />
                <span>Your password was updated. You can sign in now.</span>
              </div>
              <Link
                className="btn-primary"
                to="/login"
                style={{ textDecoration: "none" }}
                data-testid="reset-go-signin"
              >
                Go to sign in
                <ArrowRight />
              </Link>
            </>
          ) : (
            <>
              <p className="sub">
                Pick a strong password with at least 8 characters. Avoid reuse.
              </p>
              <form onSubmit={onSubmit} noValidate>
                <div className="field">
                  <label htmlFor="rp-pass">New password</label>
                  <div className="input-wrap">
                    <input
                      id="rp-pass"
                      name="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      minLength={8}
                      placeholder="Enter new password"
                      data-testid="reset-password-input"
                    />
                    <Lock className="input-icon" />
                    <button
                      type="button"
                      className="toggle-eye"
                      onClick={() => setShowPassword((s) => !s)}
                      aria-label={showPassword ? "Hide password" : "Show password"}
                      data-testid="reset-password-toggle"
                    >
                      {showPassword ? <EyeOff /> : <Eye />}
                    </button>
                  </div>
                </div>

                {error ? (
                  <div className="err" data-testid="reset-error">
                    <AlertCircle />
                    <span>{error}</span>
                  </div>
                ) : null}

                <button
                  className="btn-primary"
                  type="submit"
                  disabled={loading}
                  data-testid="reset-submit-button"
                >
                  {loading ? (
                    <>
                      <Loader2 style={{ animation: "spin 0.9s linear infinite" }} />
                      Saving…
                    </>
                  ) : (
                    <>
                      Update password
                      <ArrowRight />
                    </>
                  )}
                </button>
              </form>
            </>
          )}
          <div className="footer-links">
            <Link to="/login" data-testid="reset-back-link">
              Back to sign in
            </Link>
          </div>
        </div>
        <div className="legal-foot">Educational prototype · Not for clinical decision making</div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  );
}
