import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, ArrowRight, CheckCircle2, Loader2, Mail } from "lucide-react";
import { BrandRow } from "../components/BrandRow";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [resetUrl, setResetUrl] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");
    setResetUrl("");
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
      setMessage(data.message || "If an account exists, you can reset your password below.");
      if (data.reset_url) setResetUrl(data.reset_url);
    } catch {
      setError("Network error — please retry in a moment.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell" data-testid="forgot-page">
      <div className="grid-scaffold" aria-hidden />
      <div className="auth-wrap">
        <BrandRow envLabel="Reset password" />
        <div className="glass-card">
          <h1>Reset your password</h1>
          <p className="sub">
            Enter the email on your account. In this demo, the reset link is shown directly — no email is sent.
          </p>
          <form onSubmit={onSubmit} noValidate>
            <div className="field">
              <label htmlFor="fp-email">Email</label>
              <div className="input-wrap">
                <input
                  id="fp-email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="you@pharmacy.example"
                  data-testid="forgot-email-input"
                />
                <Mail className="input-icon" />
              </div>
            </div>

            {error ? (
              <div className="err" data-testid="forgot-error">
                <AlertCircle />
                <span>{error}</span>
              </div>
            ) : null}

            {message ? (
              <div className="notice" data-testid="forgot-notice">
                <CheckCircle2 />
                <div>
                  <div>{message}</div>
                  {resetUrl ? (
                    <div style={{ marginTop: 8 }}>
                      Demo link:{" "}
                      <code data-testid="forgot-reset-url">{resetUrl}</code>
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}

            <button
              className="btn-primary"
              type="submit"
              disabled={loading}
              data-testid="forgot-submit-button"
            >
              {loading ? (
                <>
                  <Loader2 style={{ animation: "spin 0.9s linear infinite" }} />
                  Sending…
                </>
              ) : (
                <>
                  Request reset link
                  <ArrowRight />
                </>
              )}
            </button>
          </form>
          <div className="footer-links">
            <Link to="/login" data-testid="forgot-back-link">
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
