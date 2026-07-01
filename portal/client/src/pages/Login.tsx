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

  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  function handleGoogleSignIn() {
    // Redirect to backend Google OAuth endpoint
    window.location.href = "/auth/google/login";
  }

  return (
    <div className="auth-shell" data-testid="login-page">
      <div className="grid-scaffold" aria-hidden />
      <div className="auth-wrap">
        <BrandRow envLabel="Sign in" />
        <div className="glass-card">
          <h1>Welcome back</h1>
          <p className="sub">
            Access the PairWise Rx workspace to triage prescriptions and screen drug pairs.
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

          <div style={{ margin: "20px 0", textAlign: "center", color: "#94a3b8", fontSize: "0.875rem", display: "flex", alignItems: "center", gap: "12px" }}>
            <div style={{ flex: 1, height: "1px", background: "#e2e8f0" }}></div>
            <span>or</span>
            <div style={{ flex: 1, height: "1px", background: "#e2e8f0" }}></div>
          </div>

          <button
            type="button"
            onClick={handleGoogleSignIn}
            className="btn-google"
            data-testid="google-signin-button"
            style={{
              width: "100%",
              padding: "12px 20px",
              border: "1px solid #e2e8f0",
              borderRadius: "8px",
              background: "#fff",
              color: "#1e293b",
              fontSize: "0.9375rem",
              fontWeight: 500,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "10px",
              transition: "all 0.15s",
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.background = "#f8fafc";
              e.currentTarget.style.borderColor = "#cbd5e1";
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.background = "#fff";
              e.currentTarget.style.borderColor = "#e2e8f0";
            }}
          >
            <svg width="18" height="18" viewBox="0 0 18 18">
              <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"/>
              <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z"/>
              <path fill="#FBBC05" d="M3.964 10.71c-.18-.54-.282-1.117-.282-1.71s.102-1.17.282-1.71V4.958H.957C.347 6.173 0 7.548 0 9s.348 2.827.957 4.042l3.007-2.332z"/>
              <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"/>
            </svg>
            Continue with Google
          </button>

          <div className="footer-links" style={{ marginTop: 14 }}>
            <Link to="/forgot-password" data-testid="login-forgot-link">
              Forgot password?
            </Link>
          </div>
          <div className="footer-links">
            New to PairWise Rx?{" "}
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
