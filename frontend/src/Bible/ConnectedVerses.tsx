import { Loader } from '@mantine/core';
import { IconArrowUpRight } from '@tabler/icons-react';
import { VerseRef, VersionKey, parseRef } from './useBibleData';

interface Props {
  refs: string[];
  ready: boolean;
  versions: VersionKey[];
  getText: (v: VersionKey, book: string, chapter: string, verse: string) => string | null;
  onNavigate: (ref: VerseRef) => void;
}

/** Inline panel under an expanded verse showing its most similar verses. */
export default function ConnectedVerses({ refs, ready, versions, getText, onNavigate }: Props) {
  return (
    <div className="ao-connected" onClick={(e) => e.stopPropagation()}>
      <div className="ao-connected-title">
        Connected verses{ready && refs.length > 0 ? ` · ${refs.length}` : ''}
      </div>

      {!ready ? (
        <div className="ao-connected-empty">
          <Loader size="xs" color="olive" /> Finding connections…
        </div>
      ) : refs.length === 0 ? (
        <div className="ao-connected-empty">No connected verses for this one yet.</div>
      ) : (
        refs.map((r) => {
          const parsed = parseRef(r);
          if (!parsed) return null;
          return (
            <button
              key={r}
              type="button"
              className="ao-conn-card"
              onClick={() => onNavigate(parsed)}
              title={`Go to ${r}`}
            >
              <span className="ao-conn-ref">
                {r} <IconArrowUpRight size={13} />
              </span>
              {versions.map((ver) => {
                const t = getText(ver, parsed.book, parsed.chapter, parsed.verse);
                return t ? (
                  <span key={ver} className={`ao-conn-text ao-vline-${ver}`}>
                    {t}
                  </span>
                ) : null;
              })}
            </button>
          );
        })
      )}
    </div>
  );
}
