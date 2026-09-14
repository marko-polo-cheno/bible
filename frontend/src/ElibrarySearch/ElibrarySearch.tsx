import { useState, useRef, useEffect, useCallback, Fragment } from 'react';
import {
  Text, Box, Button, Loader, TextInput, Paper, Group, Stack, Badge,
  SegmentedControl, Switch, Pill, ActionIcon, Tooltip, Anchor, Chip,
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

/** Per-run overrides for state that has not been committed yet. */
interface PipelineOpts {
  tree?: TreeKind; prefixes?: string[]; lang?: string;
  fileTypes?: string[]; formats?: string[];
}

/** Which renditions an item has (PDF / web page) — orthogonal to its medium. */
interface FormatFacet { value: string; label: string; }

/**
 * Catalog facet tree served by /elibrary/trees — medium at the top
 * (/Audio, /Document, ...) and the granular type beneath (/Audio/Sermon).
 * Same {name, value, children} shape as the category trees, so it renders with
 * the same component and matches with the same prefix logic on the server.
 */
type FileTypeNode = CategoryNode;

interface Snippet { text: string; highlights: [number, number][]; }

interface ItemResult {
  itemId: number;
  langId: number;
  title: string;
  link: string;
  legacyCategories: string[];
  taxonomyLabels: string[];
  formType: string;
  fileType: string;
  filePath: string;
  formats: string[];
  videoHost: string;
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

  // File type is a top-level scope like language, but two levels deep, so it
  // gets the same tri-state tree the categories use — selecting /Audio takes
  // every occasion under it, /Audio/Sermon takes just the one.
  const [fileTypeTree, setFileTypeTree] = useState<FileTypeNode[]>([]);
  const [fileTypes, setFileTypes] = useState<string[]>([]);

  // Format is a flat two-value facet, so chips rather than a menu — a toggle is
  // already a committed edit, nothing to close.
  const [formatFacets, setFormatFacets] = useState<FormatFacet[]>([]);
  const [formats, setFormats] = useState<string[]>([]);

  const searched = data !== null || loading;
  const refineRef = useRef<HTMLInputElement>(null);
  const latestReq = useRef(0);

  // Load trees + semantic status once.
  useEffect(() => {
    fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.ELIBRARY_TREES}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!d) return;
        setTrees({ legacy: d.legacy ?? [], taxonomy: d.taxonomy ?? [] });
        setFileTypeTree(d.fileTypes ?? []);
        setFormatFacets(d.formats ?? []);
      })
      .catch(() => {});
    fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.ELIBRARY_STATUS}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.semantic?.ready) setSemanticReady(true); })
      .catch(() => {});
  }, []);

  /** Back to the landing state, discarding anything in flight. */
  const resetResults = useCallback(() => {
    latestReq.current++;
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  const buildFullStages = useCallback((
    searchStages: Stage[],
    opts?: PipelineOpts,
  ): Stage[] => {
    const prefixes = opts?.prefixes ?? filterPrefixes;
    const tree = opts?.tree ?? filterTree;
    const out: Stage[] = [];
    if (prefixes.length > 0) {
      out.push({ type: 'filter', tree, prefixes: [...prefixes] });
    }
    out.push(...searchStages);
    return out;
  }, [filterPrefixes, filterTree]);

  const runPipeline = useCallback(async (
    searchStages: Stage[],
    opts?: PipelineOpts,
  ) => {
    const nextStages = buildFullStages(searchStages, opts);
    if (nextStages.length === 0) return;
    // Filter edits fire searches on their own now, so two can be in flight at
    // once — a slow semantic run must not overwrite the fast one that followed it.
    const reqId = ++latestReq.current;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.ELIBRARY_SEARCH}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          stages: nextStages,
          langIds: langIdsOf(opts?.lang ?? lang),
          fileTypes: opts?.fileTypes ?? fileTypes,  // [] means every type
          formats: opts?.formats ?? formats,        // [] means every rendition
          page: 0,
          size: 25,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || `Error ${res.status}`);
      }
      const json: SearchResponse = await res.json();
      if (reqId !== latestReq.current) return;
      setData(json);
      setSemanticReady(json.semanticReady);
    } catch (e: any) {
      if (reqId !== latestReq.current) return;
      setError(e.message || 'Search failed');
    } finally {
      if (reqId === latestReq.current) setLoading(false);
    }
  }, [lang, fileTypes, formats, buildFullStages]);

  /** Re-run the current search under a new top-level filter. */
  const runWithFilter = useCallback((prefixes: string[], tree?: TreeKind) => {
    if (stages.length === 0 && prefixes.length === 0) {
      resetResults();  // nothing left to search for
      return;
    }
    runPipeline(stages, { tree: tree ?? filterTree, prefixes });
  }, [stages, runPipeline, filterTree, resetResults]);

  /** Re-run under a new file-type scope, committed when the menu closes. */
  const runWithFileTypes = useCallback((next: string[]) => {
    if (stages.length === 0 && filterPrefixes.length === 0) return;
    runPipeline(stages, { fileTypes: next });
  }, [stages, filterPrefixes, runPipeline]);

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

  const refineWith = () => {
    const text = input.trim();
    if (!text) return;
    const stage: Stage = mode === 'semantic'
      ? { type: 'semantic', query: text, topK: 50 }
      : { type: 'keyword', terms: text.split(/\s*,\s*/).filter(Boolean), includeDerivatives };
    const next = [...stages, stage];
    setStages(next);
    runPipeline(next);
  };

  const clearFilters = () => {
    setFilterPrefixes([]);
    runWithFilter([]);
  };

  const removeStage = (idx: number) => {
    const next = stages.filter((_, i) => i !== idx);
    setStages(next);
    if (next.length === 0 && filterPrefixes.length === 0) { resetResults(); return; }
    runPipeline(next);
  };

  const resetAll = () => {
    setStages([]);
    setInput('');
    setFilterPrefixes([]);
    setFileTypes([]);
    setFormats([]);
    resetResults();
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
  /** "Video · Sermon" for a granular path, "Document" for a bare medium. */
  const fileTypeLabel = (path: string) => {
    for (const n of fileTypeTree) {
      if (n.value === path) return n.name;
      const child = n.children?.find(c => c.value === path);
      if (child) return `${n.name} · ${child.name}`;
    }
    return path.replace(/^\//, '').replace('/', ' · ');
  };

  // The response's own stage list says whether it was filtered; live
  // filterPrefixes can already describe the *next* search while this one renders.
  const filterStat = data?.stages[0]?.type === 'filter' ? data.stages[0] : undefined;
  const statOffset = filterStat ? 1 : 0;

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
            { label: semanticReady ? 'Smart' : 'Smart (warming…)', value: 'semantic' },
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
        <SegmentedControl
          size="xs"
          value={lang}
          onChange={(v) => {
            setLang(v);
            // Language scopes the pool the same way the category filter does,
            // so it re-runs on change too — otherwise the only way to apply it
            // is "Refine", which appends a duplicate stage.
            if (stages.length > 0 || filterPrefixes.length > 0) runPipeline(stages, { lang: v });
          }}
          data={LANG_OPTIONS}
        />
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
            onChange={(v) => {
              const tree = v as TreeKind;
              setFilterTree(tree);
              if (filterPrefixes.length === 0) return;  // nothing was filtering
              setFilterPrefixes([]);
              runWithFilter([], tree);
            }}
            data={[{ label: 'Topical', value: 'taxonomy' }, { label: 'Legacy', value: 'legacy' }]}
          />
          <CategoryTreeSelect
            data={treeData}
            selectedValues={filterPrefixes}
            onChange={setFilterPrefixes}
            onCommit={runWithFilter}
          />
        </Group>
      </Group>

      {fileTypeTree.length > 0 && (
        <Group gap="xs" mt="sm" align="center">
          <Text size="xs" c="dimmed">Type:</Text>
          <CategoryTreeSelect
            noun="type"
            data={fileTypeTree}
            selectedValues={fileTypes}
            onChange={setFileTypes}
            onCommit={runWithFileTypes}
          />
          {formatFacets.length > 0 && (
            <>
              <Text size="xs" c="dimmed" ml="sm">Available as:</Text>
              <Chip.Group
                multiple
                value={formats}
                onChange={(v) => {
                  setFormats(v);
                  if (stages.length > 0 || filterPrefixes.length > 0) runPipeline(stages, { formats: v });
                }}
              >
                <Group gap={6}>
                  {formatFacets.map(f => (
                    <Chip key={f.value} value={f.value} size="xs" variant="outline">{f.label}</Chip>
                  ))}
                </Group>
              </Chip.Group>
            </>
          )}
        </Group>
      )}
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
            {filterPrefixes.length > 0 && (
              <>
                <Pill
                  withRemoveButton
                  onRemove={clearFilters}
                  styles={{ root: { backgroundColor: '#f1f3f5', color: '#495057' } }}
                >
                  {stageChipLabel({ type: 'filter', tree: filterTree, prefixes: filterPrefixes }, filterStat)}
                </Pill>
                {stages.length > 0 && <IconChevronRight size={14} color="#bbb" />}
              </>
            )}
            {stages.map((s, i) => {
              const stat = data?.stages[statOffset + i];
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
                    {r.filePath && r.fileType !== 'Other' && (
                      <Badge size="xs" variant="light" color="teal">{fileTypeLabel(r.filePath)}</Badge>
                    )}
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
                    {r.taxonomyLabels.map(l => (
                      <Badge key={l} title={l} size="xs" variant="dot" color="indigo" styles={{ label: { textTransform: 'none' } }}>{l.split('/').filter(Boolean).slice(-1)[0]}</Badge>
                    ))}
                    {r.legacyCategories.map(c => (
                      <Badge key={c} title={c} size="xs" variant="light" color="gray" styles={{ label: { textTransform: 'none' } }}>{c.split('/').slice(-1)[0]}</Badge>
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
