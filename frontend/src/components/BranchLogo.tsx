/** Small olive-branch mark used in app bars. */
export default function BranchLogo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="16" fill="var(--ao-olive)" />
      <path
        d="M32 50 C 30 34, 34 22, 44 14"
        stroke="var(--ao-almond-cream)"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
      <ellipse cx="40" cy="22" rx="7" ry="3.4" transform="rotate(-40 40 22)" fill="var(--ao-sage-light)" />
      <ellipse cx="30" cy="32" rx="7" ry="3.4" transform="rotate(-115 30 32)" fill="var(--ao-sage)" />
      <circle cx="38" cy="38" r="5" fill="var(--ao-blossom)" />
    </svg>
  );
}
