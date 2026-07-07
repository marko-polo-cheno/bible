import { useEffect, useMemo, useState } from 'react';
import { Modal } from '@mantine/core';
import { IconArrowLeft } from '@tabler/icons-react';
import { BookInfo } from './useBibleData';

interface Props {
  opened: boolean;
  onClose: () => void;
  books: BookInfo[];
  current: { book: string; chapter: string };
  fullScreen: boolean;
  onSelect: (book: string, chapter: string) => void;
}

interface Section {
  testament: 'old' | 'new';
  group: string;
  books: BookInfo[];
}

export default function BookPicker({
  opened,
  onClose,
  books,
  current,
  fullScreen,
  onSelect,
}: Props) {
  const [viewBook, setViewBook] = useState<string | null>(null);

  // Reopen on the book list, like familiar Bible apps
  useEffect(() => {
    if (opened) setViewBook(null);
  }, [opened]);

  const sections = useMemo(() => {
    const out: Section[] = [];
    books.forEach((b) => {
      const last = out[out.length - 1];
      if (last && last.group === b.group && last.testament === b.testament) {
        last.books.push(b);
      } else {
        out.push({ testament: b.testament, group: b.group, books: [b] });
      }
    });
    return out;
  }, [books]);

  const selected = viewBook ? books.find((b) => b.name === viewBook) : null;

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      fullScreen={fullScreen}
      size="lg"
      title={
        viewBook ? (
          <span className="ao-picker-title">
            <button
              type="button"
              className="ao-picker-back"
              onClick={() => setViewBook(null)}
              aria-label="Back to books"
            >
              <IconArrowLeft size={18} />
            </button>
            {viewBook}
          </span>
        ) : (
          'Books'
        )
      }
    >
      {!selected ? (
        <div className="ao-picker">
          {sections.map((s, i) => (
            <div key={`${s.testament}-${s.group}`}>
              {(i === 0 || sections[i - 1]!.testament !== s.testament) && (
                <div className="ao-picker-testament">
                  {s.testament === 'old' ? 'Old Testament' : 'New Testament'}
                </div>
              )}
              <div className="ao-picker-group">{s.group}</div>
              <div className="ao-picker-chips">
                {s.books.map((b) => (
                  <button
                    key={b.name}
                    type="button"
                    className={`ao-chip${b.name === current.book ? ' ao-chip-active' : ''}`}
                    onClick={() => setViewBook(b.name)}
                  >
                    {b.name}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="ao-picker-chapters">
          {selected.chapters.map((c) => (
            <button
              key={c}
              type="button"
              className={`ao-chapter-cell${
                selected.name === current.book && c === current.chapter
                  ? ' ao-chip-active'
                  : ''
              }`}
              onClick={() => onSelect(selected.name, c)}
            >
              {c}
            </button>
          ))}
        </div>
      )}
    </Modal>
  );
}
