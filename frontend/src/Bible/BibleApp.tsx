import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ActionIcon,
  Button,
  Drawer,
  Loader,
  SegmentedControl,
  Stack,
  Switch,
  Text,
} from '@mantine/core';
import { useLocalStorage, useMediaQuery } from '@mantine/hooks';
import {
  IconAdjustmentsHorizontal,
  IconChevronDown,
  IconChevronLeft,
  IconChevronRight,
  IconSearch,
} from '@tabler/icons-react';
import BranchLogo from '../components/BranchLogo';
import {
  ALL_VERSIONS,
  VERSION_LABELS,
  VerseRef,
  VersionKey,
  useBibleData,
} from './useBibleData';
import BookPicker from './BookPicker';
import ConnectedVerses from './ConnectedVerses';
import SearchOverlay from './SearchOverlay';
import './bible.css';

const SETTINGS_LABELS: Record<VersionKey, string> = {
  NKJV: 'NKJV · English',
  NASB: 'NASB · English',
  chinese: '中文 · Chinese',
  pinyin: 'Pīnyīn',
};

export default function BibleApp() {
  const bible = useBibleData();
  const isMobile = useMediaQuery('(max-width: 640px)');

  const [pos, setPos] = useLocalStorage<{ book: string; chapter: string }>({
    key: 'ao-bible-pos',
    defaultValue: { book: 'John', chapter: '3' },
  });
  const [enabled, setEnabled] = useLocalStorage<VersionKey[]>({
    key: 'ao-bible-versions',
    defaultValue: ['NKJV', 'chinese'],
  });
  const [textSize, setTextSize] = useLocalStorage<'s' | 'm' | 'l'>({
    key: 'ao-bible-size',
    defaultValue: 'm',
  });

  const [pickerOpen, setPickerOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<string | null>(null);
  const scrollTarget = useRef<string | null>(null);

  const { book, chapter } = pos;
  const info = bible.bookMap.get(book);
  const verses = bible.ready ? bible.getVerses(book, chapter) : [];
  const enabledOrdered = ALL_VERSIONS.filter((v) => enabled.includes(v));
  const bookIndex = useMemo(
    () => bible.books.findIndex((b) => b.name === book),
    [bible.books, book]
  );

  const scrollToVerse = (v: string) =>
    setTimeout(
      () =>
        document
          .getElementById(`ao-v-${v}`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'center' }),
      80
    );

  const navigate = (b: string, c: string, v?: string) => {
    setExpanded(null);
    setHighlight(v ?? null);
    if (b === book && c === chapter) {
      if (v) scrollToVerse(v);
      else window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      scrollTarget.current = v ?? null;
      setPos({ book: b, chapter: c });
    }
  };

  useEffect(() => {
    const v = scrollTarget.current;
    scrollTarget.current = null;
    if (v) scrollToVerse(v);
    else window.scrollTo({ top: 0 });
  }, [book, chapter]);

  // Neighbouring chapter/book for prev-next navigation
  const peek = (dir: 1 | -1): { book: string; chapter: string } | null => {
    if (!info) return null;
    const ci = info.chapters.indexOf(chapter);
    const ni = ci + dir;
    if (ni >= 0 && ni < info.chapters.length)
      return { book, chapter: info.chapters[ni]! };
    const nb = bible.books[bookIndex + dir];
    if (!nb) return null;
    return {
      book: nb.name,
      chapter: dir === 1 ? nb.chapters[0]! : nb.chapters[nb.chapters.length - 1]!,
    };
  };

  const step = (dir: 1 | -1) => {
    const target = peek(dir);
    if (target) navigate(target.book, target.chapter);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (pickerOpen || searchOpen || settingsOpen) return;
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (e.key === 'ArrowRight') step(1);
      if (e.key === 'ArrowLeft') step(-1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const toggleVersion = (v: VersionKey, on: boolean) =>
    setEnabled((prev) => {
      const next = on ? ALL_VERSIONS.filter((x) => prev.includes(x) || x === v) : prev.filter((x) => x !== v);
      return next.length > 0 ? next : prev; // always keep at least one
    });

  const prev = peek(-1);
  const next = peek(1);

  return (
    <div className={`ao-bible ao-reader-size-${textSize}`}>
      <header className="ao-appbar">
        <Link to="/" className="ao-appbar-logo" aria-label="Home">
          <BranchLogo />
        </Link>
        <button
          type="button"
          className="ao-ref-pill"
          onClick={() => setPickerOpen(true)}
          aria-label="Choose book and chapter"
        >
          <strong>{book}</strong>
          <span>{chapter}</span>
          <IconChevronDown size={15} />
        </button>
        <div className="ao-appbar-actions">
          <ActionIcon
            variant="subtle"
            color="olive"
            size="lg"
            radius="xl"
            onClick={() => setSearchOpen(true)}
            aria-label="Search the Bible"
          >
            <IconSearch size={20} />
          </ActionIcon>
          <ActionIcon
            variant="subtle"
            color="olive"
            size="lg"
            radius="xl"
            onClick={() => setSettingsOpen(true)}
            aria-label="Reading settings"
          >
            <IconAdjustmentsHorizontal size={20} />
          </ActionIcon>
        </div>
      </header>

      {bible.error ? (
        <div className="ao-reader-loading">
          <Text c="red">Could not load the Bible data: {bible.error}</Text>
        </div>
      ) : !bible.ready ? (
        <div className="ao-reader-loading">
          <Loader color="olive" />
          <Text c="dimmed" size="sm" mt="sm">
            Gathering the scrolls…
          </Text>
        </div>
      ) : (
        <main className="ao-reader">
          <div className="ao-chapter-title">
            <h2>
              {book} {chapter}
            </h2>
            <span>
              {info?.group} · {info?.testament === 'old' ? 'Old Testament' : 'New Testament'}
            </span>
          </div>

          <div className="ao-verses">
            {verses.map((v) => {
              const isExpanded = expanded === v;
              return (
                <article
                  key={`${book}-${chapter}-${v}`}
                  id={`ao-v-${v}`}
                  className={`ao-verse${isExpanded ? ' ao-verse-open' : ''}${
                    highlight === v ? ' ao-verse-flash' : ''
                  }`}
                >
                  <div
                    className="ao-verse-main"
                    role="button"
                    tabIndex={0}
                    aria-expanded={isExpanded}
                    onClick={() => setExpanded(isExpanded ? null : v)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setExpanded(isExpanded ? null : v);
                      }
                    }}
                  >
                    <span className="ao-vnum">{v}</span>
                    <span className="ao-vtexts">
                      {enabledOrdered.map((ver) => {
                        const t = bible.getText(ver, book, chapter, v);
                        if (!t) return null;
                        return (
                          <span key={ver} className={`ao-vline ao-vline-${ver}`}>
                            {enabledOrdered.length > 1 && (
                              <em className="ao-vtag">{VERSION_LABELS[ver]}</em>
                            )}
                            {t}
                          </span>
                        );
                      })}
                    </span>
                  </div>
                  {isExpanded && (
                    <ConnectedVerses
                      refs={bible.getNeighbors(book, chapter, v)}
                      ready={bible.neighborsReady}
                      versions={enabledOrdered.slice(0, 2)}
                      getText={bible.getText}
                      onNavigate={(r: VerseRef) => navigate(r.book, r.chapter, r.verse)}
                    />
                  )}
                </article>
              );
            })}
          </div>

          <nav className="ao-chapter-nav">
            <Button
              variant="light"
              color="olive"
              disabled={!prev}
              leftSection={<IconChevronLeft size={16} />}
              onClick={() => step(-1)}
            >
              {prev ? `${prev.book} ${prev.chapter}` : 'Beginning'}
            </Button>
            <Button
              variant="light"
              color="olive"
              disabled={!next}
              rightSection={<IconChevronRight size={16} />}
              onClick={() => step(1)}
            >
              {next ? `${next.book} ${next.chapter}` : 'End'}
            </Button>
          </nav>
        </main>
      )}

      <BookPicker
        opened={pickerOpen}
        onClose={() => setPickerOpen(false)}
        books={bible.books}
        current={pos}
        fullScreen={!!isMobile}
        onSelect={(b, c) => {
          setPickerOpen(false);
          navigate(b, c);
        }}
      />

      <SearchOverlay
        opened={searchOpen}
        onClose={() => setSearchOpen(false)}
        bible={bible}
        isMobile={!!isMobile}
        onNavigate={(r) => {
          setSearchOpen(false);
          navigate(r.book, r.chapter, r.verse);
        }}
      />

      <Drawer
        opened={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        position={isMobile ? 'bottom' : 'right'}
        size={isMobile ? 'auto' : 340}
        title="Reading settings"
        padding="lg"
      >
        <Text size="sm" fw={600} mb="xs">
          Translations
        </Text>
        <Stack gap="sm" mb="xl">
          {ALL_VERSIONS.map((v) => (
            <Switch
              key={v}
              color="olive"
              label={SETTINGS_LABELS[v]}
              checked={enabled.includes(v)}
              onChange={(e) => toggleVersion(v, e.currentTarget.checked)}
            />
          ))}
        </Stack>
        <Text size="sm" fw={600} mb="xs">
          Text size
        </Text>
        <SegmentedControl
          fullWidth
          color="olive"
          value={textSize}
          onChange={(v) => setTextSize(v as 's' | 'm' | 'l')}
          data={[
            { label: 'Small', value: 's' },
            { label: 'Medium', value: 'm' },
            { label: 'Large', value: 'l' },
          ]}
        />
      </Drawer>
    </div>
  );
}
