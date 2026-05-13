import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { RxMark } from "../components/RxMark";

export default function Splash() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    const t = window.setInterval(() => setPhase((p) => (p + 1) % 4), 900);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    const t = window.setTimeout(() => {
      navigate("/login", { replace: true });
    }, 4200);
    return () => window.clearTimeout(t);
  }, [navigate]);

  return (
    <div className="splash-page">
      <div className={`splash-glow splash-glow--${phase}`} aria-hidden />
      <div className="splash-inner">
        <div className="splash-logo-wrap">
          <div className="splash-ring" />
          <RxMark size={88} />
        </div>
        <h1 className="splash-title">
          Pharma Checker<span className="splash-rx"> ℞</span>
        </h1>
        <p className="splash-tagline">Clinical workflow &amp; interaction checks — clear, calm, accountable.</p>
        <div className="splash-bar">
          <div className="splash-bar-fill" />
        </div>
        <button type="button" className="splash-cta" onClick={() => navigate("/login", { replace: true })}>
          Continue
        </button>
      </div>
      <style>{`
        .splash-page {
          min-height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 32px;
          background: radial-gradient(ellipse 80% 50% at 50% -20%, rgba(61, 156, 240, 0.25), transparent),
            linear-gradient(168deg, #04070d 0%, #0c1526 40%, #070b12 100%);
          position: relative;
          overflow: hidden;
        }
        .splash-glow {
          position: absolute;
          width: 140vmax;
          height: 140vmax;
          border-radius: 50%;
          filter: blur(80px);
          opacity: 0.35;
          transition: transform 1.2s ease, opacity 1s ease;
          pointer-events: none;
        }
        .splash-glow--0 { transform: translate(-20%, -10%); background: #3d9cf0; }
        .splash-glow--1 { transform: translate(10%, 5%); background: #5ae8c5; opacity: 0.28; }
        .splash-glow--2 { transform: translate(-5%, 15%); background: #7c5cff; opacity: 0.22; }
        .splash-glow--3 { transform: translate(15%, -25%); background: #3d9cf0; }
        .splash-inner {
          position: relative;
          text-align: center;
          max-width: 420px;
          animation: splashUp 0.9s cubic-bezier(0.22, 1, 0.36, 1) both;
        }
        @keyframes splashUp {
          from { opacity: 0; transform: translateY(28px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .splash-logo-wrap {
          position: relative;
          display: inline-flex;
          margin-bottom: 22px;
        }
        .splash-ring {
          position: absolute;
          inset: -14px;
          border-radius: 28px;
          border: 1px solid rgba(120, 180, 255, 0.25);
          animation: ringPulse 2.4s ease-in-out infinite;
        }
        @keyframes ringPulse {
          0%, 100% { transform: scale(1); opacity: 0.6; }
          50% { transform: scale(1.06); opacity: 1; }
        }
        .rx-svg { display: block; filter: drop-shadow(0 8px 24px rgba(61, 156, 240, 0.35)); }
        .splash-title {
          font-family: "Outfit", sans-serif;
          font-weight: 700;
          font-size: clamp(1.85rem, 5vw, 2.35rem);
          letter-spacing: -0.03em;
          margin: 0 0 10px;
          color: #f0f6ff;
        }
        .splash-rx {
          font-weight: 500;
          color: #5ae8c5;
          margin-left: 2px;
        }
        .splash-tagline {
          margin: 0 0 28px;
          color: #8b9bb8;
          font-size: 0.98rem;
          line-height: 1.55;
        }
        .splash-bar {
          height: 3px;
          border-radius: 3px;
          background: rgba(255, 255, 255, 0.06);
          overflow: hidden;
          margin-bottom: 22px;
        }
        .splash-bar-fill {
          height: 100%;
          width: 40%;
          border-radius: 3px;
          background: linear-gradient(90deg, #3d9cf0, #5ae8c5);
          animation: barSlide 2.2s ease-in-out infinite;
        }
        @keyframes barSlide {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(350%); }
        }
        .splash-cta {
          padding: 12px 28px;
          border-radius: 999px;
          border: 1px solid rgba(120, 180, 255, 0.35);
          background: rgba(18, 30, 52, 0.6);
          color: #e8eef8;
          font-weight: 600;
          font-size: 0.95rem;
          cursor: pointer;
          transition: background 0.15s, transform 0.12s;
        }
        .splash-cta:hover {
          background: rgba(61, 156, 240, 0.2);
          transform: translateY(-1px);
        }
      `}</style>
    </div>
  );
}
