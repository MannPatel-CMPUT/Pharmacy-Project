import { PairWiseMark } from "./PairWiseMark";

export function BrandRow({ envLabel = "Clinical Suite" }: { envLabel?: string }) {
  return (
    <div className="brand-row" data-testid="auth-brand-row">
      <div className="brand-mark" aria-hidden>
        <PairWiseMark size={22} />
      </div>
      <div className="brand-word" data-testid="auth-brand-word">
        PairWise <em>Rx</em>
      </div>
      <div className="brand-tag" data-testid="auth-brand-env">
        {envLabel}
      </div>
    </div>
  );
}
