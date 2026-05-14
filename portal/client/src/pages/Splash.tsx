import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, ShieldCheck, Activity, Pill } from "lucide-react";
import { RxMark } from "../components/RxMark";

export default function Splash() {
  const navigate = useNavigate();

  useEffect(() => {
    const t = window.setTimeout(() => {
      navigate("/login", { replace: true });
    }, 4400);
    return () => window.clearTimeout(t);
  }, [navigate]);

  return (
    <div className="splash-shell" data-testid="splash-page">
      <div className="splash-inner">
        <div className="splash-mark-wrap" aria-hidden>
          <RxMark size={44} />
        </div>
        <h1 className="splash-word" data-testid="splash-wordmark">
          Rx<em>Flow</em>
        </h1>
        <p className="splash-tagline" data-testid="splash-tagline">
          Clinical workflow and interaction screening for pharmacists.
          Clear, calm, accountable.
        </p>

        <div className="splash-meta" aria-label="Capability badges">
          <span data-testid="splash-meta-interactions">
            <Activity />
            Interaction engine
          </span>
          <span data-testid="splash-meta-workflow">
            <Pill />
            Rx workflow
          </span>
          <span data-testid="splash-meta-audit">
            <ShieldCheck />
            Audit trail
          </span>
        </div>

        <div className="splash-bar" aria-hidden>
          <div className="splash-bar-fill" />
        </div>

        <button
          type="button"
          className="splash-cta"
          onClick={() => navigate("/login", { replace: true })}
          data-testid="splash-continue-button"
        >
          Continue to sign in
          <ArrowRight />
        </button>
      </div>
    </div>
  );
}
