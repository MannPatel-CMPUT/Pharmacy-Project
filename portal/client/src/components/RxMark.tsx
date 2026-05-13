export function RxMark({ size = 72 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      className="rx-svg"
    >
      <defs>
        <linearGradient id="rxGrad" x1="12" y1="8" x2="52" y2="56" gradientUnits="userSpaceOnUse">
          <stop stopColor="#5ae8c5" />
          <stop offset="0.45" stopColor="#3d9cf0" />
          <stop offset="1" stopColor="#7c5cff" />
        </linearGradient>
        <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="2.5" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <rect x="10" y="10" width="44" height="44" rx="14" stroke="url(#rxGrad)" strokeWidth="2.2" fill="rgba(10,16,28,0.55)" filter="url(#glow)" />
      <path
        d="M22 22h8c5 0 8 3.2 8 7.5S35 37 30 37h-8M30 22v20M38 30h10M38 38h10"
        stroke="url(#rxGrad)"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
