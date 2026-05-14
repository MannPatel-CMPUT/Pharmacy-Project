import { RxMark } from "./RxMark";

export function BrandRow({ envLabel = "Clinical Suite" }: { envLabel?: string }) {
  return (
    <div className="brand-row" data-testid="auth-brand-row">
      <div className="brand-mark" aria-hidden>
        <RxMark size={22} />
      </div>
      <div className="brand-word" data-testid="auth-brand-word">
        Rx<em>Flow</em>
      </div>
      <div className="brand-tag" data-testid="auth-brand-env">
        {envLabel}
      </div>
    </div>
  );
}
