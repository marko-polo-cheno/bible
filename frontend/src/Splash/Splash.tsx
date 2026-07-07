import { useEffect, useState } from 'react';
import './Splash.css';

const SEEN_KEY = 'ao-splash-seen';
const DURATION = 2600;

/** Full-screen intro shown once per session; click to skip. */
export default function Splash() {
  const [phase, setPhase] = useState<'show' | 'leave' | 'gone'>(() =>
    sessionStorage.getItem(SEEN_KEY) ? 'gone' : 'show'
  );

  useEffect(() => {
    if (phase !== 'show') return;
    sessionStorage.setItem(SEEN_KEY, '1');
    const t = setTimeout(() => setPhase('leave'), DURATION);
    return () => clearTimeout(t);
  }, [phase]);

  if (phase === 'gone') return null;

  return (
    <div
      className={`ao-splash ${phase === 'leave' ? 'ao-splash-leave' : ''}`}
      onClick={() => setPhase('leave')}
      onTransitionEnd={() => phase === 'leave' && setPhase('gone')}
      role="presentation"
    >
      <svg className="ao-splash-branch" viewBox="0 0 320 200" aria-hidden="true">
        {/* branch */}
        <path
          className="ao-draw"
          d="M30 170 C 90 150, 140 110, 180 70 C 205 45, 240 30, 290 26"
          fill="none"
          stroke="var(--ao-almond-wood)"
          strokeWidth="3.5"
          strokeLinecap="round"
        />
        {/* leaves */}
        <g className="ao-pop" style={{ animationDelay: '0.7s' }}>
          <ellipse cx="105" cy="128" rx="16" ry="6.5" transform="rotate(-38 105 128)" fill="var(--ao-sage)" />
        </g>
        <g className="ao-pop" style={{ animationDelay: '0.9s' }}>
          <ellipse cx="150" cy="102" rx="16" ry="6.5" transform="rotate(24 150 102)" fill="var(--ao-sage-light)" />
        </g>
        <g className="ao-pop" style={{ animationDelay: '1.1s' }}>
          <ellipse cx="196" cy="58" rx="16" ry="6.5" transform="rotate(-44 196 58)" fill="var(--ao-olive)" />
        </g>
        {/* olives */}
        <circle className="ao-pop" style={{ animationDelay: '1.25s' }} cx="132" cy="122" r="7" fill="var(--ao-olive-deep)" />
        <circle className="ao-pop" style={{ animationDelay: '1.35s' }} cx="176" cy="86" r="6" fill="var(--ao-olive)" />
        {/* almond blossoms */}
        <g className="ao-pop" style={{ animationDelay: '1.5s' }}>
          <circle cx="252" cy="34" r="8" fill="var(--ao-blossom)" />
          <circle cx="252" cy="34" r="3" fill="var(--ao-almond-cream)" />
        </g>
        <g className="ao-pop" style={{ animationDelay: '1.62s' }}>
          <circle cx="285" cy="47" r="6.5" fill="var(--ao-blossom)" />
          <circle cx="285" cy="47" r="2.5" fill="var(--ao-almond-cream)" />
        </g>
      </svg>
      <div className="ao-splash-word">Almonds &amp; Olives</div>
      <div className="ao-splash-sub">almondsandolives.ca</div>
    </div>
  );
}
