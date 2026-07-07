import { useEffect, useRef, useState } from 'react';
import {
  ActionIcon,
  Button,
  Collapse,
  Drawer,
  Group,
  Loader,
  SegmentedControl,
  Text,
  Textarea,
} from '@mantine/core';
import {
  IconAdjustments,
  IconArrowUp,
  IconDownload,
  IconSearch,
  IconTrash,
} from '@tabler/icons-react';
import { useBibleChat, ChatMessage } from '../contexts/BibleChatContext';
import { API_CONFIG } from '../config/api';
import { BibleData, VerseRef } from './useBibleData';

interface Passage {
  book: string;
  chapter?: number;
  verse?: number;
  start_chapter?: number;
  start_verse?: number;
  end_chapter?: number;
  end_verse?: number;
}

interface Props {
  opened: boolean;
  onClose: () => void;
  bible: BibleData;
  isMobile: boolean;
  onNavigate: (ref: VerseRef) => void;
}

const EXAMPLES = [
  'faith during trials',
  'Jesus calms the storm',
  'a new heaven and a new earth',
];

function refString(p: Passage): string {
  if (p.chapter && p.verse) return `${p.book} ${p.chapter}:${p.verse}`;
  if (p.start_chapter !== undefined && p.end_chapter !== undefined) {
    return p.start_chapter === p.end_chapter
      ? `${p.book} ${p.start_chapter}:${p.start_verse}-${p.end_verse}`
      : `${p.book} ${p.start_chapter}:${p.start_verse} - ${p.end_chapter}:${p.end_verse}`;
  }
  return p.book;
}

function toVerseRef(p: Passage): VerseRef {
  return {
    book: p.book,
    chapter: String(p.chapter ?? p.start_chapter ?? 1),
    verse: String(p.verse ?? p.start_verse ?? 1),
  };
}

export default function SearchOverlay({ opened, onClose, bible, isMobile, onNavigate }: Props) {
  const { chatHistory, addMessage, clearChat, exportChatHistory } = useBibleChat();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [showOptions, setShowOptions] = useState(false);
  const [resultCount, setResultCount] = useState('few');
  const [contentType, setContentType] = useState('verses');
  const [modelType, setModelType] = useState('fast');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [chatHistory, loading, opened]);

  function passageText(p: Passage): string | null {
    if (p.chapter && p.verse)
      return bible.getText('NKJV', p.book, String(p.chapter), String(p.verse));
    if (
      p.start_chapter === undefined ||
      p.start_verse === undefined ||
      p.end_chapter === undefined ||
      p.end_verse === undefined
    )
      return null;
    const texts: string[] = [];
    for (let ch = p.start_chapter; ch <= p.end_chapter; ch++) {
      const verses = bible.getVerses(p.book, String(ch));
      for (const v of verses) {
        const n = +v;
        if (ch === p.start_chapter && n < p.start_verse) continue;
        if (ch === p.end_chapter && n > p.end_verse) continue;
        const t = bible.getText('NKJV', p.book, String(ch), v);
        if (t) texts.push(t);
      }
    }
    return texts.length ? texts.join(' ') : null;
  }

  async function handleSearch(q?: string) {
    const text = (q ?? query).trim();
    if (!text || loading) return;
    setLoading(true);
    addMessage({ type: 'user', content: text });
    setQuery('');
    const settings = { resultCount, contentType, modelType };
    try {
      const params = new URLSearchParams({
        query: text,
        result_count: resultCount,
        content_type: contentType,
        model_type: modelType,
      });
      const res = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.SEARCH}?${params}`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      const refs = (data.passages ?? []).map((p: Passage) => refString(p));
      addMessage({
        type: 'assistant',
        content: refs.length ? refs.join(', ') : 'No passages found — try rephrasing?',
        result: data,
        settings,
      });
    } catch (err) {
      addMessage({
        type: 'assistant',
        content: `Something went wrong: ${err instanceof Error ? err.message : err}`,
        settings,
      });
    } finally {
      setLoading(false);
    }
  }

  function renderPassageCards(passages: Passage[] | undefined, muted = false) {
    if (!passages?.length) return null;
    return passages.map((p, i) => {
      const t = passageText(p);
      return (
        <button
          key={refString(p) + i}
          type="button"
          className={`ao-conn-card ao-search-card${muted ? ' ao-search-card-muted' : ''}`}
          onClick={() => onNavigate(toVerseRef(p))}
          title="Read in context"
        >
          <span className="ao-conn-ref">{refString(p)}</span>
          <span className="ao-conn-text ao-vline-NKJV">{t ?? 'Open to read this passage.'}</span>
        </button>
      );
    });
  }

  function renderMessage(m: ChatMessage) {
    if (m.type === 'user') {
      return (
        <div key={m.id} className="ao-msg-user">
          {m.content}
        </div>
      );
    }
    return (
      <div key={m.id} className="ao-msg-assistant">
        {!m.result && <Text size="sm">{m.content}</Text>}
        {m.result && (
          <>
            {renderPassageCards(m.result.passages)}
            {m.result.secondary_passages?.length > 0 && (
              <>
                <div className="ao-connected-title" style={{ marginTop: 10 }}>
                  Also see
                </div>
                {renderPassageCards(m.result.secondary_passages, true)}
              </>
            )}
          </>
        )}
      </div>
    );
  }

  return (
    <Drawer
      opened={opened}
      onClose={onClose}
      position="right"
      size={isMobile ? '100%' : 480}
      title="Search the Bible"
      padding="md"
      classNames={{ body: 'ao-search-body' }}
    >
      <div className="ao-search-toolbar">
        <ActionIcon
          variant={showOptions ? 'light' : 'subtle'}
          color="olive"
          radius="xl"
          onClick={() => setShowOptions((s) => !s)}
          aria-label="Search options"
        >
          <IconAdjustments size={18} />
        </ActionIcon>
        {chatHistory.length > 0 && (
          <Group gap={4}>
            <ActionIcon variant="subtle" color="olive" radius="xl" onClick={exportChatHistory} aria-label="Export chat">
              <IconDownload size={18} />
            </ActionIcon>
            <ActionIcon variant="subtle" color="red" radius="xl" onClick={clearChat} aria-label="Clear chat">
              <IconTrash size={18} />
            </ActionIcon>
          </Group>
        )}
      </div>

      <Collapse in={showOptions}>
        <div className="ao-search-options">
          <div>
            <Text size="xs" fw={600} mb={4}>
              Results
            </Text>
            <SegmentedControl
              size="xs"
              color="olive"
              value={resultCount}
              onChange={setResultCount}
              data={[
                { label: 'One', value: 'one' },
                { label: 'Few', value: 'few' },
                { label: 'Many', value: 'many' },
              ]}
            />
          </div>
          <div>
            <Text size="xs" fw={600} mb={4}>
              Content
            </Text>
            <SegmentedControl
              size="xs"
              color="olive"
              value={contentType}
              onChange={setContentType}
              data={[
                { label: 'Verses', value: 'verses' },
                { label: 'Passages', value: 'passages' },
                { label: 'All', value: 'all' },
              ]}
            />
          </div>
          <div>
            <Text size="xs" fw={600} mb={4}>
              Model
            </Text>
            <SegmentedControl
              size="xs"
              color="olive"
              value={modelType}
              onChange={setModelType}
              data={[
                { label: 'Fast', value: 'fast' },
                { label: 'Advanced', value: 'advanced' },
              ]}
            />
          </div>
        </div>
      </Collapse>

      <div className="ao-search-scroll" ref={scrollRef}>
        {chatHistory.length === 0 && !loading ? (
          <div className="ao-search-empty">
            <IconSearch size={28} stroke={1.4} />
            <Text size="sm" c="dimmed" ta="center">
              Ask anything — a story, a theme, or the half-remembered words of a verse.
            </Text>
            <div className="ao-search-examples">
              {EXAMPLES.map((ex) => (
                <Button
                  key={ex}
                  size="compact-sm"
                  variant="light"
                  color="olive"
                  radius="xl"
                  onClick={() => handleSearch(ex)}
                >
                  {ex}
                </Button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {chatHistory.map(renderMessage)}
            {loading && (
              <div className="ao-msg-assistant ao-search-loading">
                <Loader size="xs" color="olive" /> Searching the Scriptures…
              </div>
            )}
          </>
        )}
      </div>

      <div className="ao-search-inputrow">
        <Textarea
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          placeholder="Search by meaning…"
          autosize
          minRows={1}
          maxRows={4}
          style={{ flex: 1 }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSearch();
            }
          }}
        />
        <ActionIcon
          size={40}
          radius="xl"
          color="olive"
          variant="filled"
          onClick={() => handleSearch()}
          disabled={!query.trim() || loading}
          aria-label="Send"
        >
          <IconArrowUp size={20} />
        </ActionIcon>
      </div>
    </Drawer>
  );
}
