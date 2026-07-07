import { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  IconBook2,
  IconLibrary,
  IconLanguage,
  IconMap2,
  IconMessageHeart,
} from '@tabler/icons-react';
import './HomePage.css';

interface Tile {
  title: string;
  blurb: string;
  icon: ReactNode;
  to?: string;
  accent: string; // CSS gradient for live tiles
}

const LIVE: Tile[] = [
  {
    title: 'Bible',
    blurb: 'Read, connect and search the Scriptures',
    icon: <IconBook2 size={30} stroke={1.6} />,
    to: '/bible',
    accent: 'linear-gradient(135deg, var(--ao-sage) 0%, var(--ao-olive) 100%)',
  },
  {
    title: 'eLibrary',
    blurb: 'Sermons, publications & testimonies',
    icon: <IconLibrary size={30} stroke={1.6} />,
    to: '/elibrary',
    accent: 'linear-gradient(135deg, var(--ao-almond-cream) 0%, var(--ao-blossom) 100%)',
  },
];

const SOON: Tile[] = [
  {
    title: 'Live Translator',
    blurb: 'Real-time sermon translation',
    icon: <IconLanguage size={26} stroke={1.6} />,
    accent: '',
  },
  {
    title: 'The Journey',
    blurb: 'Walk the Bible chronologically, on a living map',
    icon: <IconMap2 size={26} stroke={1.6} />,
    accent: '',
  },
  {
    title: 'Sabbath Notes',
    blurb: 'Share takeaways verse by verse, together',
    icon: <IconMessageHeart size={26} stroke={1.6} />,
    accent: '',
  },
];

function HomePage() {
  return (
    <div className="ao-home">
      <header className="ao-home-hero">
        <svg className="ao-home-mark" viewBox="0 0 64 64" aria-hidden="true">
          <path d="M32 54 C 29 36, 34 22, 46 12" stroke="var(--ao-almond-wood)" strokeWidth="3" strokeLinecap="round" fill="none" />
          <ellipse cx="40" cy="24" rx="9" ry="4.2" transform="rotate(-40 40 24)" fill="var(--ao-sage-light)" />
          <ellipse cx="28" cy="36" rx="9" ry="4.2" transform="rotate(-115 28 36)" fill="var(--ao-sage)" />
          <circle cx="39" cy="41" r="6" fill="var(--ao-olive-deep)" />
          <circle cx="48" cy="17" r="5" fill="var(--ao-blossom)" />
          <circle cx="48" cy="17" r="2" fill="var(--ao-almond-cream)" />
        </svg>
        <h1>Almonds &amp; Olives</h1>
        <p>A small orchard of tools for studying the Bible.</p>
      </header>

      <main className="ao-home-grid">
        {LIVE.map((t) => (
          <Link key={t.title} to={t.to!} className="ao-tile ao-tile-live">
            <div className="ao-tile-icon" style={{ background: t.accent }}>
              {t.icon}
            </div>
            <div className="ao-tile-body">
              <h2>{t.title}</h2>
              <p>{t.blurb}</p>
            </div>
            <span className="ao-tile-arrow" aria-hidden="true">
              →
            </span>
          </Link>
        ))}

        <div className="ao-home-soon-row">
          {SOON.map((t) => (
            <div key={t.title} className="ao-tile ao-tile-soon" aria-disabled="true">
              <div className="ao-tile-icon ao-tile-icon-soon">{t.icon}</div>
              <div className="ao-tile-body">
                <h2>
                  {t.title} <span className="ao-soon-badge">soon</span>
                </h2>
                <p>{t.blurb}</p>
              </div>
            </div>
          ))}
        </div>
      </main>

      <footer className="ao-home-footer">
        “The harvest truly is plentiful…” — Matthew 9:37
      </footer>
    </div>
  );
}

export default HomePage;
