import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertCircle, ArrowRight, Eye, EyeOff, Lock, Loader2, User } from "lucide-react";
import { BrandRow } from "../components/BrandRow";

export default function Login() {
  const [params] = useSearchParams();
  const next = params.get("next") || "/workspace";
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
              : "Sign in failed.";
        setError(msg);
        return;
      }
      window.location.href = next.startsWith("/") ? next : "/workspace";
    } catch {
      setError("Network error — please retry in a moment.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell" data-testid="login-page">
      <div className="grid-scaffold" aria-hidden />
      <div className="auth-wrap">
        <BrandRow envLabel="Sign in" />
        <div className="glass-card">
          <h1>Welcome back</h1>
          <p className="sub">
            Access the RxFlow workspace to triage prescriptions and screen interactions.
          </p>
          <form onSubmit={onSubmit} noValidate>
            <div className="field">
              <label htmlFor="username">Username</label>
              <div className="input-wrap">
                <input
                  id="username"
                  name="username"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. mariap"
                  required
                  data-testid="login-username-input"
                />
                <User className="input-icon" />
              </div>
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <div className="input-wrap">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  data-testid="login-password-input"
                />
                <Lock className="input-icon" />
                <button
                  type="button"
                  className="toggle-eye"
                  onClick={() => setShowPassword((s) => !s)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  data-testid="login-password-toggle"
                >
                  {showPassword ? <EyeOff /> : <Eye />}
                </button>
              </div>
            </div>

            {error ? (
              <div className="err" data-testid="login-error">
                <AlertCircle />
                <span>{error}</span>
              </div>
            ) : null}

            <button
              className="btn-primary"
              type="submit"
              disabled={loading}
              data-testid="login-submit-button"
            >
              {loading ? (
                <>
                  <Loader2 style={{ animation: "spin 0.9s linear infinite" }} />
                  Signing in…
                </>
              ) : (
                <>
                  Sign in
                  <ArrowRight />
                </>
              )}
            </button>
          </form>
          <div className="footer-links" style={{ marginTop: 14 }}>
            <Link to="/forgot-password" data-testid="login-forgot-link">
              Forgot password?
            </Link>
          </div>
          <div className="footer-links">
            New to RxFlow?{" "}
            <Link to="/signup" data-testid="login-signup-link">
              Create an account
            </Link>
          </div>
        </div>
        <div className="legal-foot" data-testid="login-legal">
          Educational prototype · Not for clinical decision making
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  );
}
