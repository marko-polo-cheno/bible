import { useEffect, useMemo, useState } from 'react';

export type VersionKey = 'NKJV' | 'NASB' | 'chinese' | 'pinyin';
export const ALL_VERSIONS: VersionKey[] = ['NKJV', 'NASB', 'chinese', 'pinyin'];
export const VERSION_LABELS: Record<VersionKey, string> = {
  NKJV: 'NKJV',
  NASB: 'NASB',
  chinese: '中文',
  pinyin: 'Pīnyīn',
};

type RawBible = {
  [testament: string]: {
    [group: string]: {
      [book: string]: { [chapter: string]: { [verse: string]: string } };
    };
  };
};

type Neighbors = {
  [book: string]: { [chapter: string]: { [verse: string]: string[] } };
};

export interface BookInfo {
  name: string;
  testament: 'old' | 'new';
  group: string;
  chapters: string[];
}

export interface VerseRef {
  book: string;
  chapter: string;
  verse: string;
}

export function parseRef(ref: string): VerseRef | null {
  const m = ref.match(/^(.+) (\d+):(\d+)$/);
  return m ? { book: m[1]!, chapter: m[2]!, verse: m[3]! } : null;
}

export function useBibleData() {
  const [versions, setVersions] = useState<Partial<Record<VersionKey, RawBible>>>({});
  const [neighbors, setNeighbors] = useState<Neighbors | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const loaded = await Promise.all(
          ALL_VERSIONS.map(async (v) => {
            const res = await fetch(`data/${v}.json`);
            if (!res.ok) throw new Error(`Failed to load ${v} (${res.status})`);
            return [v, (await res.json()) as RawBible] as const;
          })
        );
        if (alive) setVersions(Object.fromEntries(loaded));
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
      try {
        const res = await fetch('data/nn.json');
        if (res.ok) {
          const nn = (await res.json()) as Neighbors;
          if (alive) setNeighbors(nn);
        }
      } catch {
        // connected verses simply stay unavailable
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const nkjv = versions.NKJV;

  const books = useMemo<BookInfo[]>(() => {
    if (!nkjv) return [];
    const out: BookInfo[] = [];
    (['old', 'new'] as const).forEach((testament) => {
      Object.entries(nkjv[testament] || {}).forEach(([group, groupBooks]) => {
        Object.entries(groupBooks).forEach(([name, chapters]) => {
          out.push({ name, testament, group, chapters: Object.keys(chapters) });
        });
      });
    });
    return out;
  }, [nkjv]);

  const bookMap = useMemo(() => new Map(books.map((b) => [b.name, b])), [books]);

  const getText = (
    version: VersionKey,
    book: string,
    chapter: string,
    verse: string
  ): string | null => {
    const data = versions[version];
    const info = bookMap.get(book);
    if (!data || !info) return null;
    return data[info.testament]?.[info.group]?.[book]?.[chapter]?.[verse] ?? null;
  };

  const getVerses = (book: string, chapter: string): string[] => {
    const info = bookMap.get(book);
    if (!info || !nkjv) return [];
    const chapterData = nkjv[info.testament]?.[info.group]?.[book]?.[chapter] ?? {};
    return Object.keys(chapterData).sort((a, b) => +a - +b);
  };

  const getNeighbors = (book: string, chapter: string, verse: string): string[] =>
    neighbors?.[book]?.[chapter]?.[verse] ?? [];

  return {
    ready: books.length > 0,
    error,
    books,
    bookMap,
    getText,
    getVerses,
    getNeighbors,
    neighborsReady: neighbors !== null,
  };
}

export type BibleData = ReturnType<typeof useBibleData>;
