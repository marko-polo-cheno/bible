import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Text, Box, Button, Loader, Textarea, Paper, Group, ScrollArea,
  Collapse, Stack, Switch, Badge, CloseButton, Tooltip,
  SegmentedControl, Select
} from '@mantine/core';
import { styles } from '../BibleNavigator/BibleNavigator.styles';
import { useTestimoniesChat, ChatMessage } from '../contexts/TestimoniesChatContext';
import { API_CONFIG } from '../config/api';

interface TestimonyResult {
  filename: string;
  link: string;
  hitCount: number;
  preview: string;
  categories: string[];
}

interface TestimoniesSearchResponse {
  searchTerms: string[];
  results: TestimonyResult[];
  derivativesIncluded?: boolean;
}

/** A term with its pre-computed derivatives from the backend. */
interface EnrichedTerm {
  term: string;
  derivatives: string[];
}

/** Response from GET /testimonies-suggest. No separate derivatives param — each item has derivatives inline. */
interface TestimoniesSuggestResponse {
  queryTerms: EnrichedTerm[];
  suggestions: EnrichedTerm[];
}

export default function TestimoniesSearch() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Search options
  const [includeDerivatives, setIncludeDerivatives] = useState(false);
  const [useAiSuggestions, setUseAiSuggestions] = useState(true);

  // Language & category filters
  const [langId, setLangId] = useState<number>(1);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const lang = langId === 2 ? "zh" : "en";
  const isChinese = langId === 2;

  // Data from /testimonies-suggest (derivatives pre-computed for everything)
  const [queryTermsEnriched, setQueryTermsEnriched] = useState<EnrichedTerm[]>([]);
  const [suggestionsEnriched, setSuggestionsEnriched] = useState<EnrichedTerm[]>([]);
  /** Which AI-suggested terms are currently selected (by term string). */
  const [selectedSuggestions, setSelectedSuggestions] = useState<Set<string>>(new Set());

  const { chatHistory, addMessage, toggleMessageCollapse, clearChat, exportChatHistory } = useTestimoniesChat();
  const scrollAreaRef = useRef<HTMLDivElement>(null);

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
    fetchCategories(langId);
  }, [langId, fetchCategories]);

  const handleLanguageChange = useCallback((value: string) => {
    const newLangId = value === "Chinese" ? 2 : 1;
    setLangId(newLangId);
    setSelectedCategory(null);
    setQuery("");
    setQueryTermsEnriched([]);
    setSuggestionsEnriched([]);
    setSelectedSuggestions(new Set());
    setIncludeDerivatives(false);
    setError(null);
    clearChat();
  }, [clearChat]);

  // When AI toggle is turned off, deselect all suggestions (but keep data cached)
  useEffect(() => {
    if (!useAiSuggestions) {
      setSelectedSuggestions(new Set());
    } else {
      setSelectedSuggestions(new Set(suggestionsEnriched.map(s => s.term)));
    }
  }, [useAiSuggestions]);

  const toggleSuggestion = (term: string) => {
    setSelectedSuggestions(prev => {
      const next = new Set(prev);
      if (next.has(term)) {
        next.delete(term);
      } else {
        next.add(term);
      }
      return next;
    });
  };

  const removeSuggestion = (term: string) => {
    setSuggestionsEnriched(prev => prev.filter(s => s.term !== term));
    setSelectedSuggestions(prev => {
      const next = new Set(prev);
      next.delete(term);
      return next;
    });
  };

  /**
   * Assemble the final flat term list that gets sent to /testimonies-search.
   * When override is provided (e.g. from suggest response in handleSearch), use it; else use state.
   */
  function buildSearchTerms(override?: {
    queryTermsEnriched: EnrichedTerm[];
    suggestionsEnriched: EnrichedTerm[];
    selectedSuggestions: Set<string>;
    query: string;
  }): string[] {
    const qTerms = override?.queryTermsEnriched ?? queryTermsEnriched;
    const sEnriched = override?.suggestionsEnriched ?? suggestionsEnriched;
    const sel = override?.selectedSuggestions ?? selectedSuggestions;
    const q = override?.query ?? query;

    const terms: string[] = [];
    const seen = new Set<string>();

    const addUnique = (t: string) => {
      const lower = t.toLowerCase();
      if (!seen.has(lower)) {
        seen.add(lower);
        terms.push(t);
      }
    };

    for (const qt of qTerms) {
      addUnique(qt.term);
      if (includeDerivatives) {
        for (const d of qt.derivatives) addUnique(d);
      }
    }

    if (qTerms.length === 0) {
      for (const t of q.trim().split(/\s*,\s*/).filter(Boolean)) {
        addUnique(t);
      }
    }

    if (useAiSuggestions) {
      for (const sg of sEnriched) {
        if (sel.has(sg.term)) {
          addUnique(sg.term);
          if (includeDerivatives) {
            for (const d of sg.derivatives) addUnique(d);
          }
        }
      }
    }

    return terms;
  }

  const handleSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setSuggesting(true);

    const queryToUse = query.trim();
    const derivativesWereOn = includeDerivatives;
    addMessage({ type: 'user', content: query });

    let queryTermsEnrichedFromSuggest: EnrichedTerm[] = [];
    let suggestionsEnrichedFromSuggest: EnrichedTerm[] = [];
    let selectedFromSuggest = new Set<string>();

    if (useAiSuggestions) {
      try {
        const suggestParams = new URLSearchParams({ query: queryToUse, lang });
        const suggestRes = await fetch(
          `${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.TESTIMONIES_SUGGEST}?${suggestParams}`
        );
        if (suggestRes.ok) {
          const suggestData: TestimoniesSuggestResponse = await suggestRes.json();
          queryTermsEnrichedFromSuggest = suggestData.queryTerms ?? [];
          suggestionsEnrichedFromSuggest = suggestData.suggestions ?? [];
          selectedFromSuggest = new Set(suggestData.suggestions?.map(s => s.term) ?? []);
          setQueryTermsEnriched(queryTermsEnrichedFromSuggest);
          setSuggestionsEnriched(suggestionsEnrichedFromSuggest);
          setSelectedSuggestions(selectedFromSuggest);
        }
      } catch {
        queryTermsEnrichedFromSuggest = [];
        suggestionsEnrichedFromSuggest = [];
        selectedFromSuggest = new Set();
      }
    }
    setSuggesting(false);

    const termsToSend = buildSearchTerms({
      queryTermsEnriched: queryTermsEnrichedFromSuggest,
      suggestionsEnriched: suggestionsEnrichedFromSuggest,
      selectedSuggestions: selectedFromSuggest,
      query: queryToUse,
    });
    setQuery("");

    try {
      const params = new URLSearchParams({
        terms: termsToSend.join(","),
        lang_id: String(langId),
      });
      if (selectedCategory) params.set("category", selectedCategory);
      const apiUrl = `${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.TESTIMONIES_SEARCH}?${params}`;
      const res = await fetch(apiUrl);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data: TestimoniesSearchResponse = await res.json();

      const resultsText = data.results.length > 0
        ? `Found ${data.results.length} testimonies`
        : 'No testimonies found';
      const summaryText = `Searched ${data.searchTerms.length} terms${derivativesWereOn ? ' (incl. derivatives)' : ''}. ${resultsText}.`;

      addMessage({ type: 'assistant', content: summaryText, result: { ...data, derivativesIncluded: derivativesWereOn } });
      setError(null);
    } catch (err: any) {
      const errorMessage = err.message || 'Unknown error';
      setError(errorMessage);
      addMessage({ type: 'assistant', content: `Error: ${errorMessage}` });
    } finally {
      setLoading(false);
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
            {result.preview && (
              <Text size="sm" c="dimmed" mb="xs" lineClamp={3}>{result.preview}</Text>
            )}
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

  function renderSuggestionBadge(sg: EnrichedTerm) {
    const isSelected = selectedSuggestions.has(sg.term);
    return (
      <Tooltip key={sg.term} label={isSelected ? 'Click to exclude' : 'Click to include'} withArrow>
        <Badge
          variant={isSelected ? 'filled' : 'outline'}
          color={isSelected ? 'blue' : 'gray'}
          size="lg"
          style={{ cursor: 'pointer', paddingRight: 3 }}
          onClick={() => toggleSuggestion(sg.term)}
          rightSection={
            <CloseButton
              size="xs"
              variant="transparent"
              c={isSelected ? 'white' : 'gray'}
              onClick={(e) => { e.stopPropagation(); removeSuggestion(sg.term); }}
            />
          }
        >
          {sg.term}
        </Badge>
      </Tooltip>
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
            placeholder="Enter search terms, comma-separated (e.g. exam, school, stress)..."
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
          <Button onClick={handleSearch} loading={loading} disabled={!query.trim()} color="blue" size={size}>
            Search
          </Button>
        </Group>

        {/* Options row */}
        <Group gap="lg" mb={useAiSuggestions && suggestionsEnriched.length > 0 ? 'sm' : 0}>
          {!isChinese && (
            <Switch
              label="Include word derivatives"
              description="Also match plurals, past tense, etc."
              checked={includeDerivatives}
              onChange={e => setIncludeDerivatives(e.currentTarget.checked)}
              size="sm"
            />
          )}
          <Switch
            label="AI suggested terms"
            description="Expand search with related words"
            checked={useAiSuggestions}
            onChange={e => setUseAiSuggestions(e.currentTarget.checked)}
            size="sm"
          />
        </Group>

        {/* AI suggested terms */}
        {useAiSuggestions && (query.trim() || suggestionsEnriched.length > 0) && (
          <Box>
            {suggesting ? (
              <Group gap="xs">
                <Loader size="xs" />
                <Text size="xs" c="dimmed">Getting suggestions...</Text>
              </Group>
            ) : suggestionsEnriched.length > 0 ? (
              <>
                <Text size="xs" c="dimmed" mb={4}>
                  AI suggestions — click to toggle, ✕ to remove:
                </Text>
                <Group gap={8} style={{ flexWrap: 'wrap', alignItems: 'flex-start' }}>
                  {suggestionsEnriched.map(sg => renderSuggestionBadge(sg))}
                </Group>
              </>
            ) : null}
          </Box>
        )}
      </Paper>
    );
  }

  return (
    <Box style={styles.container}>
      <Text size="xl" fw="bold" mb="md">Testimonies Search</Text>

      {/* Settings bar */}
      <Paper shadow="xs" p="md" mb="md" radius="md" withBorder>
        <Group justify="space-between" mb="xs">
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
        <Group gap="md" align="flex-end">
          <Box>
            <Text size="xs" c="dimmed" mb={4}>Language</Text>
            <SegmentedControl
              value={langId === 2 ? "Chinese" : "English"}
              onChange={handleLanguageChange}
              data={["English", "Chinese"]}
              size="sm"
            />
          </Box>
          <Select
            label="Category"
            placeholder="All categories"
            data={categories}
            value={selectedCategory}
            onChange={setSelectedCategory}
            clearable
            searchable
            size="sm"
            style={{ minWidth: 220 }}
            styles={{ label: { fontSize: 'var(--mantine-font-size-xs)', color: 'var(--mantine-color-dimmed)' } }}
          />
        </Group>
      </Paper>

      {/* Chat Interface */}
      <Box style={{ maxWidth: '66.67%', margin: '0 auto', height: 'calc(100vh - 180px)', display: 'flex', flexDirection: 'column' }}>
        {chatHistory.length === 0 ? (
          <Stack gap="lg" style={{ flex: 1, justifyContent: 'center' }}>
            <Paper shadow="xs" p="xl" radius="md" withBorder style={{ textAlign: 'center' }}>
              <Text size="lg" c="dimmed">Search through testimonies</Text>
              <Text size="sm" c="dimmed" mt="xs">
                Enter search terms to find relevant testimonies. Use commas to separate multiple terms.
              </Text>
            </Paper>
            {renderSearchControls('lg')}
          </Stack>
        ) : (
          <>
            <ScrollArea ref={scrollAreaRef} style={{ flex: 1, marginBottom: '1rem' }} scrollbarSize={6}>
              {chatHistory.map(message => renderChatMessage(message))}
              {loading && (
                <Box mb="md">
                  <Paper shadow="xs" p="md" radius="md" withBorder style={{ marginRight: '20%' }}>
                    <Group>
                      <Loader size="sm" color="blue" />
                      <Text size="sm" c="dimmed">Searching testimonies...</Text>
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
