import { useState, useRef, useEffect, useCallback, Fragment } from 'react';
import {
  Text, Box, Button, Loader, TextInput, Paper, Group, Stack, Badge,
  SegmentedControl, Switch, Pill, ActionIcon, Tooltip, Anchor,
} from '@mantine/core';
import { API_CONFIG } from '../config/api';
import { IconSearch, IconChevronRight, IconX } from '@tabler/icons-react';
import CategoryTreeSelect, { type CategoryNode } from '../TestimoniesSearch/CategoryTreeSelect';

type TreeKind = 'legacy' | 'taxonomy';
type Mode = 'keyword' | 'semantic';

interface Stage {
  type: 'keyword' | 'semantic' | 'filter';
  // keyword
  terms?: string[];
  includeDerivatives?: boolean;
  // semantic
  query?: string;
  topK?: number;
  // filter
  tree?: TreeKind;
  prefixes?: string[];
}

interface StageStat {
  type: string;
  label: string;
  inCount: number;
  outCount: number;
  scored: boolean;
  available: boolean;
}

interface Snippet { text: string; highlights: [number, number][]; }

interface ItemResult {
  itemId: number;
  langId: number;
  title: string;
  link: string;
  legacyCategories: string[];
  taxonomyLabels: string[];
  formType: string;
  score: number | null;
  hitCount: number;
  snippets: Snippet[];
}

interface SearchResponse {
  stages: StageStat[];
  total: number;
  page: number;
  size: number;
  results: ItemResult[];
  semanticReady: boolean;
}

const LANG_OPTIONS = [
  { label: 'EN + 中文', value: 'both' },
  { label: 'English', value: 'en' },
  { label: '中文', value: 'zh' },
];

function langIdsOf(lang: string): number[] | null {
  if (lang === 'en') return [1];
  if (lang === 'zh') return [2];
  return null; // both
}

export default function ElibrarySearch() {
  const [lang, setLang] = useState('both');
  const [mode, setMode] = useState<Mode>('keyword');
  const [input, setInput] = useState('');
  const [includeDerivatives, setIncludeDerivatives] = useState(false);

  const [stages, setStages] = useState<Stage[]>([]);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [semanticReady, setSemanticReady] = useState(false);

  // Trees for the filter stage.
  const [trees, setTrees] = useState<{ legacy: CategoryNode[]; taxonomy: CategoryNode[] }>({ legacy: [], taxonomy: [] });
  const [filterTree, setFilterTree] = useState<TreeKind>('taxonomy');
  const [filterPrefixes, setFilterPrefixes] = useState<string[]>([]);

  const searched = data !== null || loading;
  const refineRef = useRef<HTMLInputElement>(null);

  // Load trees + semantic status once.
  useEffect(() => {
    fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.ELIBRARY_TREES}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setTrees({ legacy: d.legacy ?? [], taxonomy: d.taxonomy ?? [] }); })
      .catch(() => {});
    fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.ELIBRARY_STATUS}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.semantic?.ready) setSemanticReady(true); })
      .catch(() => {});
  }, []);

  const runPipeline = useCallback(async (nextStages: Stage[]) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.ELIBRARY_SEARCH}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stages: nextStages, langIds: langIdsOf(lang), page: 0, size: 25 }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || `Error ${res.status}`);
      }
      const json: SearchResponse = await res.json();
      setData(json);
      setSemanticReady(json.semanticReady);
    } catch (e: any) {
      setError(e.message || 'Search failed');
    } finally {
      setLoading(false);
    }
  }, [lang]);

  const buildFirstStage = (): Stage | null => {
    const text = input.trim();
    if (!text) return null;
    if (mode === 'semantic') return { type: 'semantic', query: text, topK: 50 };
    const terms = text.split(/\s*,\s*/).filter(Boolean);
    return { type: 'keyword', terms, includeDerivatives };
  };

  const startSearch = () => {
    const first = buildFirstStage();
    if (!first) return;
    const next = [first];
    setStages(next);
    runPipeline(next);
  };

  const addRefinement = (stage: Stage) => {
    const next = [...stages, stage];
    setStages(next);
    runPipeline(next);
    setInput('');
  };

  const refineWith = () => {
    const text = input.trim();
    if (!text) return;
    if (mode === 'semantic') {
      addRefinement({ type: 'semantic', query: text, topK: 50 });
    } else {
      addRefinement({ type: 'keyword', terms: text.split(/\s*,\s*/).filter(Boolean), includeDerivatives });
    }
  };

  const applyFilter = () => {
    if (filterPrefixes.length === 0) return;
    addRefinement({ type: 'filter', tree: filterTree, prefixes: filterPrefixes });
    setFilterPrefixes([]);
  };

  const removeStage = (idx: number) => {
    const next = stages.filter((_, i) => i !== idx);
    setStages(next);
    if (next.length === 0) { setData(null); return; }
    runPipeline(next);
  };

  const resetAll = () => {
    setStages([]);
    setData(null);
    setInput('');
    setFilterPrefixes([]);
  };

  function renderSnippet(s: Snippet, i: number) {
    if (!s.highlights || s.highlights.length === 0) {
      return <Fragment key={i}>{i > 0 && <span style={{ color: '#bbb' }}> … </span>}{s.text}</Fragment>;
    }
    const parts: React.ReactNode[] = [];
    let cursor = 0;
    for (const [start, end] of s.highlights) {
      if (start > cursor) parts.push(s.text.slice(cursor, start));
      parts.push(<mark key={start} style={{ backgroundColor: '#fff3bf', padding: '0 1px', borderRadius: 2 }}>{s.text.slice(start, end)}</mark>);
      cursor = end;
    }
    if (cursor < s.text.length) parts.push(s.text.slice(cursor));
    return <Fragment key={i}>{i > 0 && <span style={{ color: '#bbb' }}> … </span>}{parts}</Fragment>;
  }

  function stageChipLabel(s: Stage, stat?: StageStat): string {
    if (stat) return `${stat.label}  ·  ${stat.inCount.toLocaleString()} → ${stat.outCount.toLocaleString()}`;
    if (s.type === 'filter') return `filter · ${s.tree} · ${s.prefixes?.length ?? 0}`;
    if (s.type === 'semantic') return `smart · "${(s.query ?? '').slice(0, 30)}"`;
    return `keyword · ${(s.terms ?? []).join(', ')}`;
  }

  const treeData = filterTree === 'taxonomy' ? trees.taxonomy : trees.legacy;

  // ----- search bar (shared) -----
  const renderBar = (big: boolean) => (
    <Paper shadow={big ? 'md' : 'xs'} p={big ? 'lg' : 'md'} radius="lg" withBorder>
      <Group gap="sm" align="center">
        <SegmentedControl
          size={big ? 'sm' : 'xs'}
          value={mode}
          onChange={(v) => setMode(v as Mode)}
          data={[
            { label: 'Keyword', value: 'keyword' },
            { label: semanticReady ? 'Smart (RAG)' : 'Smart (warming…)', value: 'semantic' },
          ]}
        />
        <TextInput
          ref={big ? undefined : refineRef}
          style={{ flex: 1, minWidth: 180 }}
          size={big ? 'md' : 'sm'}
          radius="xl"
          placeholder={mode === 'semantic'
            ? 'Describe what you’re looking for…'
            : 'Keywords (comma-separated). e.g. healing, prayer'}
          value={input}
          onChange={e => setInput(e.currentTarget.value)}
          onKeyDown={e => { if (e.key === 'Enter') { searched ? refineWith() : startSearch(); } }}
          leftSection={<IconSearch size={16} />}
        />
        <Button radius="xl" size={big ? 'md' : 'sm'} onClick={searched ? refineWith : startSearch} loading={loading}>
          {searched ? 'Refine' : 'Search'}
        </Button>
      </Group>

      <Group gap="lg" mt="sm" align="center">
        <SegmentedControl size="xs" value={lang} onChange={setLang} data={LANG_OPTIONS} />
        {mode === 'keyword' && (
          <Switch
            size="xs"
            label="Word derivatives"
            checked={includeDerivatives}
            onChange={e => setIncludeDerivatives(e.currentTarget.checked)}
          />
        )}
        <Group gap="xs" align="center">
          <SegmentedControl
            size="xs"
            value={filterTree}
            onChange={(v) => { setFilterTree(v as TreeKind); setFilterPrefixes([]); }}
            data={[{ label: 'Topical', value: 'taxonomy' }, { label: 'Legacy', value: 'legacy' }]}
          />
          <CategoryTreeSelect data={treeData} selectedValues={filterPrefixes} onChange={setFilterPrefixes} />
          <Button size="xs" variant="light" disabled={filterPrefixes.length === 0} onClick={applyFilter}>
            {searched ? 'Add filter' : 'Filter'}
          </Button>
        </Group>
      </Group>
    </Paper>
  );

  return (
    <Box style={{ maxWidth: 880, margin: '0 auto', padding: '0 1rem' }}>
      {!searched ? (
        <Stack gap="lg" style={{ minHeight: '60vh', justifyContent: 'center' }}>
          <Box ta="center">
            <Text fz={34} fw={600}>eLibrary Search</Text>
            <Text c="dimmed" mt={4}>Keyword, filter, and semantic search across 24,000+ items — stack them to narrow.</Text>
          </Box>
          {renderBar(true)}
        </Stack>
      ) : (
        <Stack gap="md" pt="md">
          {renderBar(false)}

          {/* Pipeline funnel chips */}
          <Group gap="xs" align="center">
            <Text size="xs" c="dimmed">Pipeline:</Text>
            {stages.map((s, i) => {
              const stat = data?.stages[i];
              const unavailable = stat && !stat.available;
              return (
                <Fragment key={i}>
                  {i > 0 && <IconChevronRight size={14} color="#bbb" />}
                  <Pill
                    withRemoveButton
                    onRemove={() => removeStage(i)}
                    styles={{ root: { backgroundColor: unavailable ? '#fff0f0' : '#eef3ff', color: unavailable ? '#c92a2a' : '#1c3d80' } }}
                  >
                    {stageChipLabel(s, stat)}
                  </Pill>
                </Fragment>
              );
            })}
            <Button size="compact-xs" variant="subtle" color="gray" onClick={resetAll} ml="auto">Reset</Button>
          </Group>

          {error && (
            <Paper p="sm" radius="md" withBorder style={{ backgroundColor: '#ffe6e6' }}>
              <Group justify="space-between">
                <Text size="sm" c="red">{error}</Text>
                <ActionIcon variant="subtle" color="red" onClick={() => setError(null)} aria-label="Dismiss"><IconX size={16} /></ActionIcon>
              </Group>
            </Paper>
          )}

          {data && (
            <Text size="sm" c="dimmed">{data.total.toLocaleString()} result{data.total === 1 ? '' : 's'}</Text>
          )}

          {loading && (
            <Group gap="xs"><Loader size="sm" /><Text size="sm" c="dimmed">Searching…</Text></Group>
          )}

          <Stack gap="sm">
            {data?.results.map((r) => (
              <Paper key={`${r.langId}-${r.itemId}`} p="md" radius="md" withBorder>
                <Group justify="space-between" align="flex-start" wrap="nowrap">
                  <Anchor href={r.link} target="_blank" rel="noopener noreferrer" fw={500} fz="md" style={{ lineHeight: 1.3 }}>
                    {r.title || `Item ${r.itemId}`}
                  </Anchor>
                  <Group gap={6} wrap="nowrap">
                    <Badge size="xs" variant="light" color="gray">{r.langId === 2 ? '中文' : 'EN'}</Badge>
                    {r.hitCount > 0 && <Badge size="xs" variant="light" color="blue">{r.hitCount} hits</Badge>}
                    {r.score != null && r.hitCount === 0 && (
                      <Tooltip label="semantic similarity"><Badge size="xs" variant="light" color="grape">{r.score.toFixed(2)}</Badge></Tooltip>
                    )}
                  </Group>
                </Group>

                {r.snippets.length > 0 && (
                  <Text size="sm" c="dimmed" mt={6} style={{ lineHeight: 1.6 }}>
                    {r.snippets.map((s, i) => renderSnippet(s, i))}
                  </Text>
                )}

                {(r.taxonomyLabels.length > 0 || r.legacyCategories.length > 0) && (
                  <Group gap={6} mt={8}>
                    {r.taxonomyLabels.slice(0, 3).map(l => (
                      <Badge key={l} size="xs" variant="dot" color="indigo" styles={{ label: { textTransform: 'none' } }}>{l.split('/').filter(Boolean).slice(-1)[0]}</Badge>
                    ))}
                    {r.legacyCategories.slice(0, 2).map(c => (
                      <Badge key={c} size="xs" variant="light" color="gray" styles={{ label: { textTransform: 'none' } }}>{c.split('/').slice(-1)[0]}</Badge>
                    ))}
                  </Group>
                )}
              </Paper>
            ))}
            {data && data.results.length === 0 && !loading && (
              <Text c="dimmed" ta="center" py="xl">No items match this pipeline. Try removing a stage.</Text>
            )}
          </Stack>
        </Stack>
      )}
    </Box>
  );
}
