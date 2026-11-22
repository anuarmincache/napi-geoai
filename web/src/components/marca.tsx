/** Marca do portal em SVG. Não reproduz logotipo de terceiros. */
export function MarcaNapi({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} role="img" aria-label="NAPI GeoAI">
      <defs>
        <linearGradient id="mg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2f4a33" />
          <stop offset="1" stopColor="#73a535" />
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r="30" fill="url(#mg)" />
      <path
        d="M32 10a22 22 0 1 0 15.6 6.4"
        fill="none"
        stroke="#ffffff"
        strokeWidth="4.5"
        strokeLinecap="round"
      />
      <circle cx="32" cy="32" r="12" fill="none" stroke="#ffffff" strokeWidth="3" />
      <path d="M34 16 L22 36 h8 l-3 14 14-20h-8z" fill="#fcc817" />
      <path
        d="M42 44c-6 0-10 3-11 8 6 1 10-1 12-4 3 1 6 0 8-3-3-2-6-2-9-1z"
        fill="#ffffff"
      />
    </svg>
  );
}
