import { useState, useRef, useEffect, useCallback, Fragment } from 'react';
import {
  Text, Box, Button, Loader, Textarea, Paper, Group, ScrollArea,
  Collapse, Stack, Switch, Badge, CloseButton, Tooltip,
  SegmentedControl, Pill, TagsInput, ActionIcon,
} from '@mantine/core';
import { styles } from '../BibleNavigator/BibleNavigator.styles';
import { useTestimoniesChat, ChatMessage } from '../contexts/TestimoniesChatContext';
import { API_CONFIG } from '../config/api';
import CategoryTreeSelect, { type CategoryNode } from './CategoryTreeSelect';

interface Snippet {
  text: string;
  highlights: [number, number][];
}

interface TestimonyResult {
  filename: string;
  link: string;
  hitCount: number;
  preview: string;
  snippets?: Snippet[];
  categories: string[];
}

interface TestimoniesSearchResponse {
  searchTerms: string[];
  results: TestimonyResult[];
  derivativesIncluded?: boolean;
}

interface EnrichedTerm {
  term: string;
  derivatives: string[];
}

interface AnalyzeResponse {
  langIds: number[];
  categoriesEn: string[];
  categoriesZh: string[];
  termsEn: EnrichedTerm[];
  termsZh: EnrichedTerm[];
  includeDerivatives: boolean;
}

export default function TestimoniesSearch() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Active terms (from LLM or manual) displayed as pills
  const [activeTerms, setActiveTerms] = useState<EnrichedTerm[]>([]);
  const [includeDerivatives, setIncludeDerivatives] = useState(false);

  // Advanced settings state
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [manualLang, setManualLang] = useState<string>("Auto");
  const [manualTerms, setManualTerms] = useState<string[]>([]);
  const [categories, setCategories] = useState<CategoryNode[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [categoriesLangId, setCategoriesLangId] = useState<number>(1);

  const { chatHistory, addMessage, toggleMessageCollapse, clearChat, exportChatHistory } = useTestimoniesChat();
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Fetch categories when advanced language changes
  const fetchCategories = useCallback(async (lid: number) => {
    try {
      const params = new URLSearchParams({ lang_id: String(lid) });
      const res = await fetch(
        `${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.TESTIMONIES_CATEGORIES}?${params}`
      );
      if (res.ok) {
        const data = await res.json();
        setCategories(data.categories ?? []);
      }
    } catch {
      setCategories([]);
    }
  }, []);

  useEffect(() => {
    fetchCategories(categoriesLangId);
  }, [categoriesLangId, fetchCategories]);

  // When manual language changes in advanced, update categories lang
  const handleAdvancedLangChange = useCallback((value: string) => {
    setManualLang(value);
    if (value === "English") {
      setCategoriesLangId(1);
    } else if (value === "Chinese") {
      setCategoriesLangId(2);
    }
    setSelectedCategories([]);
  }, []);

  const removeActiveTerm = (term: string) => {
    setActiveTerms(prev => prev.filter(t => t.term !== term));
  };

  const addManualTerm = (term: string) => {
    const trimmed = term.trim();
    if (!trimmed) return;
    setActiveTerms(prev => {
      if (prev.some(t => t.term.toLowerCase() === trimmed.toLowerCase())) return prev;
      return [...prev, { term: trimmed, derivatives: [] }];
    });
  };

  const handleSearch = async () => {
    if (!query.trim() && activeTerms.length === 0 && manualTerms.length === 0) return;

    setLoading(true);
    setError(null);

    const queryText = query.trim();
    if (queryText) {
      addMessage({ type: 'user', content: queryText });
    }

    const isAdvancedManual = advancedOpen && manualLang !== "Auto";

    try {
      let langIds: number[] = [];
      let searchCategoriesEn: string[] = [];
      let searchCategoriesZh: string[] = [];
      let termsToSearch: EnrichedTerm[] = [...activeTerms];
      let derivativesFlag = includeDerivatives;

      if (queryText && !isAdvancedManual) {
        // Use unified LLM analyze
        setAnalyzing(true);
        try {
          const analyzeParams = new URLSearchParams({ query: queryText });
          const analyzeRes = await fetch(
            `${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.TESTIMONIES_ANALYZE}?${analyzeParams}`
          );
          if (analyzeRes.ok) {
            const analysis: AnalyzeResponse = await analyzeRes.json();

            // Use LLM-detected values, but respect manual overrides
            langIds = analysis.langIds;
            searchCategoriesEn = analysis.categoriesEn;
            searchCategoriesZh = analysis.categoriesZh;
            derivativesFlag = analysis.includeDerivatives;

            // Merge LLM terms with any existing active terms
            const existingTermSet = new Set(termsToSearch.map(t => t.term.toLowerCase()));
            for (const t of [...analysis.termsEn, ...analysis.termsZh]) {
              if (!existingTermSet.has(t.term.toLowerCase())) {
                termsToSearch.push(t);
                existingTermSet.add(t.term.toLowerCase());
              }
            }
            setActiveTerms(termsToSearch);
            setIncludeDerivatives(derivativesFlag);
          }
        } catch {
          // Fallback: parse query as comma-separated terms
          const fallbackTerms = queryText.split(/\s*,\s*/).filter(Boolean);
          for (const t of fallbackTerms) {
            if (!termsToSearch.some(et => et.term.toLowerCase() === t.toLowerCase())) {
              termsToSearch.push({ term: t, derivatives: [] });
            }
          }
          langIds = [1]; // default to English
        }
        setAnalyzing(false);
      } else if (isAdvancedManual) {
        // Manual mode: use advanced settings
        langIds = manualLang === "English" ? [1] : manualLang === "Chinese" ? [2] : [1, 2];

        // Add manual terms as active terms
        for (const t of manualTerms) {
          if (!termsToSearch.some(et => et.term.toLowerCase() === t.toLowerCase())) {
            termsToSearch.push({ term: t, derivatives: [] });
          }
        }

        // If user typed a query, also parse it
        if (queryText) {
          const parsed = queryText.split(/\s*,\s*/).filter(Boolean);
          for (const t of parsed) {
            if (!termsToSearch.some(et => et.term.toLowerCase() === t.toLowerCase())) {
              termsToSearch.push({ term: t, derivatives: [] });
            }
          }
        }
      } else {
        // No query text, just active terms — default to English
        langIds = [1];
      }

      // Override with advanced settings if set
      if (advancedOpen && manualLang !== "Auto") {
        langIds = manualLang === "English" ? [1] : manualLang === "Chinese" ? [2] : [1, 2];
      }
      if (advancedOpen && selectedCategories.length > 0) {
        // Use manually selected categories for all languages
        searchCategoriesEn = selectedCategories;
        searchCategoriesZh = selectedCategories;
      }

      if (termsToSearch.length === 0) {
        setError("No search terms found. Please enter a query.");
        setLoading(false);
        return;
      }

      // Build flat term list
      const flatTerms: string[] = [];
      const seen = new Set<string>();
      for (const t of termsToSearch) {
        const lower = t.term.toLowerCase();
        if (!seen.has(lower)) {
          seen.add(lower);
          flatTerms.push(t.term);
        }
        if (derivativesFlag) {
          for (const d of t.derivatives) {
            const dl = d.toLowerCase();
            if (!seen.has(dl)) {
              seen.add(dl);
              flatTerms.push(d);
            }
          }
        }
      }

      // Execute search for each language
      const allResults: TestimonyResult[] = [];
      const searchPromises = langIds.map(async (lid) => {
        const cats = lid === 1 ? searchCategoriesEn : searchCategoriesZh;
        const params = new URLSearchParams({
          terms: flatTerms.join(","),
          lang_id: String(lid),
          snippets: "true",
        });
        if (cats.length > 0) params.set("categories", cats.join("|"));
        const apiUrl = `${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.TESTIMONIES_SEARCH}?${params}`;
        const res = await fetch(apiUrl);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const data: TestimoniesSearchResponse = await res.json();
        return data;
      });

      const searchResults = await Promise.all(searchPromises);
      for (const data of searchResults) {
        allResults.push(...data.results);
      }
      // Sort merged results by hit count
      allResults.sort((a, b) => b.hitCount - a.hitCount);

      const allSearchTerms = searchResults.flatMap(r => r.searchTerms);
      const resultsText = allResults.length > 0
        ? `Found ${allResults.length} testimonies`
        : 'No testimonies found';
      const langLabel = langIds.length === 2 ? "EN+ZH" : langIds[0] === 2 ? "ZH" : "EN";
      const summaryText = `Searched ${flatTerms.length} terms (${langLabel})${derivativesFlag ? ' incl. derivatives' : ''}. ${resultsText}.`;

      const combinedResponse: TestimoniesSearchResponse = {
        searchTerms: allSearchTerms,
        results: allResults,
        derivativesIncluded: derivativesFlag,
      };
      addMessage({ type: 'assistant', content: summaryText, result: combinedResponse });
      setQuery("");
      setError(null);
    } catch (err: any) {
      const errorMessage = err.message || 'Unknown error';
      setError(errorMessage);
      addMessage({ type: 'assistant', content: `Error: ${errorMessage}` });
    } finally {
      setLoading(false);
      setAnalyzing(false);
    }
  };

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [chatHistory]);

  function formatTimestamp(date: Date): string {
    const d = new Date(date);
    d.setSeconds(0, 0);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function renderSnippet(snippet: Snippet) {
    const parts: React.ReactNode[] = [];
    let cursor = 0;
    for (const [start, end] of snippet.highlights) {
      if (start > cursor) parts.push(snippet.text.slice(cursor, start));
      parts.push(
        <mark key={start} style={{ backgroundColor: '#fff3bf', padding: '0 1px', borderRadius: 2 }}>
          {snippet.text.slice(start, end)}
        </mark>
      );
      cursor = end;
    }
    if (cursor < snippet.text.length) parts.push(snippet.text.slice(cursor));
    return <>{parts}</>;
  }

  function renderTestimoniesResults(results: TestimonyResult[] | undefined, isCollapsed: boolean = false) {
    if (!results || results.length === 0) return <Text>No testimonies found.</Text>;
    if (isCollapsed) return <Text size="sm" c="dimmed">{results.length} testimonies found</Text>;

    return (
      <>
        {results.slice(0, 10).map((result, idx) => (
          <Paper key={`${result.filename}-${idx}`} shadow="xs" p="sm" mb="sm" radius="md" withBorder>
            <Group justify="space-between" mb="xs">
              <Text size="md" fw="bold">{result.filename}</Text>
              <Text size="sm" c="blue">{result.hitCount} hits</Text>
            </Group>
            {result.snippets && result.snippets.length > 0 ? (
              <Text size="sm" c="dimmed" mb="xs" style={{ lineHeight: 1.6 }}>
                {result.snippets.map((s, i) => (
                  <Fragment key={i}>
                    {i > 0 && <span style={{ color: '#999' }}> ... </span>}
                    {renderSnippet(s)}
                  </Fragment>
                ))}
              </Text>
            ) : result.preview ? (
              <Text size="sm" c="dimmed" mb="xs" lineClamp={3}>{result.preview}</Text>
            ) : null}
            {result.categories && result.categories.length > 0 && (
              <Group gap={6} mb="xs">
                {result.categories.map(cat => (
                  <Badge key={cat} size="xs" variant="light" color="gray">{cat}</Badge>
                ))}
              </Group>
            )}
            {result.link && (
              <Text size="sm" c="dimmed" style={{ wordBreak: 'break-all' }}>
                <a href={result.link} target="_blank" rel="noopener noreferrer" style={{ color: '#1976d2' }}>
                  {result.link}
                </a>
              </Text>
            )}
          </Paper>
        ))}
        {results.length > 10 && (
          <Text size="sm" c="dimmed" mt="sm">
            ... and {results.length - 10} more testimonies
          </Text>
        )}
      </>
    );
  }

  function renderChatMessage(message: ChatMessage) {
    const isCollapsed = message.collapsed || false;

    return (
      <Box key={message.id} mb="md">
        <Paper
          shadow="xs" p="md" radius="md" withBorder
          style={{
            backgroundColor: message.type === 'user' ? '#f8f9fa' : '#ffffff',
            marginLeft: message.type === 'user' ? '20%' : '0',
            marginRight: message.type === 'user' ? '0' : '20%'
          }}
        >
          <Group justify="space-between" mb="xs">
            <Text size="sm" fw={500} c={message.type === 'user' ? 'blue' : 'green'}>
              {message.type === 'user' ? 'You' : 'Results'}
            </Text>
            <Text size="xs" c="dimmed">{formatTimestamp(message.timestamp)}</Text>
          </Group>

          <Text size="md" mb={message.result ? "sm" : 0}>{message.content}</Text>

          {message.result && (
            <Box>
              <Button variant="subtle" size="xs" onClick={() => toggleMessageCollapse(message.id)} mb="sm">
                {isCollapsed ? 'Show' : 'Hide'} Results
              </Button>
              <Collapse in={!isCollapsed}>
                <Box>
                  <Text size="sm" c="dimmed" mb="md">
                    Search used {(message.result as TestimoniesSearchResponse).searchTerms.length} terms.
                    {(message.result as TestimoniesSearchResponse).derivativesIncluded && (
                      <> Derivatives were included in the search but are not listed here.</>
                    )}
                  </Text>
                  <Text size="lg" fw="bold" mb="sm">Testimonies</Text>
                  <Box style={styles.verseDisplay} mb="sm">
                    {renderTestimoniesResults((message.result as TestimoniesSearchResponse).results, isCollapsed)}
                  </Box>
                </Box>
              </Collapse>
            </Box>
          )}
        </Paper>
      </Box>
    );
  }

  function renderActiveTermsPills() {
    if (activeTerms.length === 0 && !analyzing) return null;

    return (
      <Box mb="sm">
        {analyzing ? (
          <Group gap="xs">
            <Loader size="xs" />
            <Text size="xs" c="dimmed">Analyzing query...</Text>
          </Group>
        ) : (
          <>
            <Text size="xs" c="dimmed" mb={4}>
              Search terms — click x to remove, type below to add:
            </Text>
            <Group gap={6} style={{ flexWrap: 'wrap' }}>
              {activeTerms.map(t => (
                <Pill
                  key={t.term}
                  withRemoveButton
                  onRemove={() => removeActiveTerm(t.term)}
                  size="md"
                  styles={{
                    root: {
                      backgroundColor: t.derivatives.length > 0 ? '#e7f5ff' : '#f1f3f5',
                      color: t.derivatives.length > 0 ? '#1971c2' : '#495057',
                    },
                  }}
                >
                  {t.term}
                  {t.derivatives.length > 0 && (
                    <Text span size="xs" c="dimmed" ml={2}>+{t.derivatives.length}</Text>
                  )}
                </Pill>
              ))}
            </Group>
            <TagsInput
              placeholder="Add term (type + Enter or comma)"
              value={[]}
              onChange={(vals) => {
                for (const v of vals) addManualTerm(v);
              }}
              splitChars={[',']}
              size="xs"
              mt="xs"
              styles={{
                input: { minHeight: 30 },
              }}
            />
          </>
        )}
      </Box>
    );
  }

  function renderSearchControls(size: 'lg' | 'md' = 'md') {
    return (
      <Paper shadow={size === 'lg' ? 'md' : 'xs'} p={size === 'lg' ? 'lg' : 'md'} radius="md" withBorder>
        {/* Input row */}
        <Group align="flex-end" mb="sm">
          <Textarea
            value={query}
            onChange={e => setQuery(e.currentTarget.value)}
            placeholder="Ask about testimonies (e.g. healing from cancer, 受洗見證)..."
            style={{ flex: 1 }}
            styles={styles.autocomp}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSearch();
              }
            }}
            minRows={size === 'lg' ? 2 : 1}
            maxRows={4}
            size={size}
          />
          <Button onClick={handleSearch} loading={loading} disabled={!query.trim() && activeTerms.length === 0} color="blue" size={size}>
            Search
          </Button>
        </Group>

        {/* Active terms pills */}
        {renderActiveTermsPills()}

        {/* Advanced settings toggle */}
        <Box>
          <Button
            variant="subtle"
            size="xs"
            color="gray"
            onClick={() => setAdvancedOpen(o => !o)}
            leftSection={<Text size="xs">{advancedOpen ? '▼' : '▶'}</Text>}
          >
            Advanced Settings
          </Button>
          <Collapse in={advancedOpen}>
            <Paper p="sm" mt="xs" radius="sm" style={{ backgroundColor: '#f8f9fa' }}>
              <Group gap="md" align="flex-end" mb="sm">
                <Box>
                  <Text size="xs" c="dimmed" mb={4}>Language</Text>
                  <SegmentedControl
                    value={manualLang}
                    onChange={handleAdvancedLangChange}
                    data={["Auto", "English", "Chinese"]}
                    size="xs"
                  />
                </Box>
                {manualLang !== "Auto" && (
                  <Box>
                    <Text size="xs" c="dimmed" mb={4}>Category</Text>
                    <CategoryTreeSelect
                      data={categories}
                      selectedValues={selectedCategories}
                      onChange={setSelectedCategories}
                    />
                  </Box>
                )}
              </Group>
              <Group gap="lg">
                <Switch
                  label="Include word derivatives"
                  description="Also match plurals, past tense, etc."
                  checked={includeDerivatives}
                  onChange={e => setIncludeDerivatives(e.currentTarget.checked)}
                  size="sm"
                />
              </Group>
              {manualLang !== "Auto" && (
                <Box mt="sm">
                  <Text size="xs" c="dimmed" mb={4}>Manual search terms</Text>
                  <TagsInput
                    placeholder="Add terms (comma-separated)"
                    value={manualTerms}
                    onChange={setManualTerms}
                    splitChars={[',']}
                    size="sm"
                  />
                </Box>
              )}
            </Paper>
          </Collapse>
        </Box>
      </Paper>
    );
  }

  return (
    <Box style={styles.container}>
      <Text size="xl" fw="bold" mb="md">Testimonies Search</Text>

      {/* Settings bar */}
      <Paper shadow="xs" p="md" mb="md" radius="md" withBorder>
        <Group justify="space-between">
          <Text size="sm" c="dimmed">
            Search through 21,000+ testimonies and publications
          </Text>
          {chatHistory.length > 0 && (
            <Group gap="xs">
              <Button variant="outline" size="xs" color="blue" onClick={exportChatHistory}>Export Chat</Button>
              <Button variant="outline" size="xs" color="red" onClick={clearChat}>Clear History</Button>
            </Group>
          )}
        </Group>
      </Paper>

      {/* Chat Interface */}
      <Box style={{ maxWidth: '66.67%', margin: '0 auto', height: 'calc(100vh - 180px)', display: 'flex', flexDirection: 'column' }}>
        {chatHistory.length === 0 ? (
          <Stack gap="lg" style={{ flex: 1, justifyContent: 'center' }}>
            <Paper shadow="xs" p="xl" radius="md" withBorder style={{ textAlign: 'center' }}>
              <Text size="lg" c="dimmed">Search through testimonies</Text>
              <Text size="sm" c="dimmed" mt="xs">
                Type a question or topic. Language, categories, and keywords are automatically detected.
              </Text>
            </Paper>
            {renderSearchControls('lg')}
          </Stack>
        ) : (
          <>
            <ScrollArea ref={scrollAreaRef} style={{ flex: 1, marginBottom: '1rem' }} scrollbarSize={6}>
              {chatHistory.map(message => renderChatMessage(message))}
              {(loading || analyzing) && (
                <Box mb="md">
                  <Paper shadow="xs" p="md" radius="md" withBorder style={{ marginRight: '20%' }}>
                    <Group>
                      <Loader size="sm" color="blue" />
                      <Text size="sm" c="dimmed">
                        {analyzing ? 'Analyzing your query...' : 'Searching testimonies...'}
                      </Text>
                    </Group>
                  </Paper>
                </Box>
              )}
              {error && (
                <Box mb="md">
                  <Paper shadow="xs" p="md" radius="md" withBorder style={{ marginRight: '20%', backgroundColor: '#ffe6e6' }}>
                    <Group>
                      <Text size="sm" c="red" fw={500}>Error: {error}</Text>
                      <Button variant="subtle" size="xs" color="red" onClick={() => setError(null)}>Dismiss</Button>
                    </Group>
                  </Paper>
                </Box>
              )}
            </ScrollArea>
            {renderSearchControls('md')}
          </>
        )}
      </Box>
    </Box>
  );
}
