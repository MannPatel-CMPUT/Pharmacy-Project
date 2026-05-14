/** PairWise Rx — two linked capsules (drug pair / interaction screening). */
export function PairWiseMark({ size = 24 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <rect x="2.5" y="8" width="7.5" height="8" rx="2.5" />
      <path d="M10 12h4" />
      <rect x="14" y="8" width="7.5" height="8" rx="2.5" />
    </svg>
  );
}
