export function RxMark({ size = 24 }: { size?: number }) {
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
      {/* Stylized Rx — straight, calm, clinical */}
      <path d="M7 4h4.5a3.5 3.5 0 0 1 0 7H7" />
      <path d="M7 4v16" />
      <path d="M10 11l6 9" />
      <path d="M14 14l-3.5 -3.5" />
    </svg>
  );
}
