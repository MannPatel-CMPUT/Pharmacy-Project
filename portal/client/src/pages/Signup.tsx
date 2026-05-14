import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, ArrowRight, Eye, EyeOff, Loader2, Lock, Mail, Phone, User } from "lucide-react";
import { BrandRow } from "../components/BrandRow";

export default function Signup() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
        let msg = "Could not create your account.";
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
      setError("Network error — please retry in a moment.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell" data-testid="signup-page">
      <div className="grid-scaffold" aria-hidden />
      <div className="auth-wrap" style={{ maxWidth: 480 }}>
        <BrandRow envLabel="Create account" />
        <div className="glass-card">
          <h1>Create your account</h1>
          <p className="sub">
            Set up a workspace login. Use a strong password you do not reuse elsewhere.
          </p>
          <form onSubmit={onSubmit} noValidate>
            <div className="grid-2">
              <div className="field" style={{ marginBottom: 0 }}>
                <label htmlFor="su-user">Username</label>
                <div className="input-wrap">
                  <input
                    id="su-user"
                    name="username"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    minLength={2}
                    placeholder="mariap"
                    data-testid="signup-username-input"
                  />
                  <User className="input-icon" />
                </div>
              </div>
              <div className="field" style={{ marginBottom: 0 }}>
                <label htmlFor="su-phone">Phone</label>
                <div className="input-wrap">
                  <input
                    id="su-phone"
                    name="phone"
                    type="tel"
                    autoComplete="tel"
                    placeholder="(555) 123-4567"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    required
                    data-testid="signup-phone-input"
                  />
                  <Phone className="input-icon" />
                </div>
              </div>
            </div>

            <div className="field" style={{ marginTop: 14 }}>
              <label htmlFor="su-email">Email</label>
              <div className="input-wrap">
                <input
                  id="su-email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="you@pharmacy.example"
                  data-testid="signup-email-input"
                />
                <Mail className="input-icon" />
              </div>
            </div>

            <div className="field">
              <label htmlFor="su-pass">Password (min 8 chars)</label>
              <div className="input-wrap">
                <input
                  id="su-pass"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  placeholder="Choose a strong password"
                  data-testid="signup-password-input"
                />
                <Lock className="input-icon" />
                <button
                  type="button"
                  className="toggle-eye"
                  onClick={() => setShowPassword((s) => !s)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  data-testid="signup-password-toggle"
                >
                  {showPassword ? <EyeOff /> : <Eye />}
                </button>
              </div>
            </div>

            {error ? (
              <div className="err" data-testid="signup-error">
                <AlertCircle />
                <span>{error}</span>
              </div>
            ) : null}

            <button
              className="btn-primary"
              type="submit"
              disabled={loading}
              data-testid="signup-submit-button"
            >
              {loading ? (
                <>
                  <Loader2 style={{ animation: "spin 0.9s linear infinite" }} />
                  Creating account…
                </>
              ) : (
                <>
                  Create account
                  <ArrowRight />
                </>
              )}
            </button>
          </form>
          <div className="footer-links">
            Already registered?{" "}
            <Link to="/login" data-testid="signup-login-link">
              Sign in
            </Link>
          </div>
        </div>
        <div className="legal-foot">Educational prototype · Not for clinical decision making</div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  );
}
