import { useState, useRef, useEffect } from 'react';
import {
  Text, Box, Button, Loader, Textarea, Paper, Group, ScrollArea,
  Collapse, Stack, Switch, Badge, CloseButton, Tooltip
} from '@mantine/core';
import { styles } from '../BibleNavigator/BibleNavigator.styles';
import { useTestimoniesChat, ChatMessage } from '../contexts/TestimoniesChatContext';
import { API_CONFIG } from '../config/api';

interface TestimonyResult {
  filename: string;
  link: string;
  hitCount: number;
}

interface TestimoniesSearchResponse {
  searchTerms: string[];
  results: TestimonyResult[];
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

  // Data from /testimonies-suggest (derivatives pre-computed for everything)
  const [queryTermsEnriched, setQueryTermsEnriched] = useState<EnrichedTerm[]>([]);
  const [suggestionsEnriched, setSuggestionsEnriched] = useState<EnrichedTerm[]>([]);
  /** Which AI-suggested terms are currently selected (by term string). */
  const [selectedSuggestions, setSelectedSuggestions] = useState<Set<string>>(new Set());

  const { chatHistory, addMessage, toggleMessageCollapse, clearChat, exportChatHistory } = useTestimoniesChat();
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Fetch AI suggestions + query-term derivatives when query changes
  useEffect(() => {
    if (!query.trim()) {
      setQueryTermsEnriched([]);
      setSuggestionsEnriched([]);
      setSelectedSuggestions(new Set());
      return;
    }

    // If AI suggestions are off we still want query-term derivatives,
    // but we can skip the API call and compute nothing (derivatives
    // for user terms are returned by the suggest endpoint too).
    // For simplicity, always call the suggest endpoint — it returns
    // queryTerms even when AI suggestions are shown or hidden.
    // The frontend just hides the suggestions section when the toggle is off.

    const debounce = setTimeout(async () => {
      setSuggesting(true);
      try {
        const params = new URLSearchParams({ query: query.trim() });
        const res = await fetch(
          `${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.TESTIMONIES_SUGGEST}?${params}`
        );
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const data: TestimoniesSuggestResponse = await res.json();

        setQueryTermsEnriched(data.queryTerms ?? []);
        setSuggestionsEnriched(data.suggestions ?? []);
        setSelectedSuggestions(new Set(data.suggestions.map(s => s.term)));
      } catch {
        setQueryTermsEnriched([]);
        setSuggestionsEnriched([]);
        setSelectedSuggestions(new Set());
      } finally {
        setSuggesting(false);
      }
    }, 600);

    return () => clearTimeout(debounce);
  }, [query]);

  // When AI toggle is turned off, deselect all suggestions (but keep data cached)
  useEffect(() => {
    if (!useAiSuggestions) {
      setSelectedSuggestions(new Set());
    } else {
      // Re-select all when toggled back on
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
   *
   * Order: user's query terms first, then selected AI terms alphabetically.
   * If "include derivatives" is on, each term is followed by its derivatives.
   */
  function buildSearchTerms(): string[] {
    const terms: string[] = [];
    const seen = new Set<string>();

    const addUnique = (t: string) => {
      const lower = t.toLowerCase();
      if (!seen.has(lower)) {
        seen.add(lower);
        terms.push(t);
      }
    };

    // 1. User's own query terms (preserve their typed order)
    for (const qt of queryTermsEnriched) {
      addUnique(qt.term);
      if (includeDerivatives) {
        for (const d of qt.derivatives) addUnique(d);
      }
    }

    // Fallback: if suggest hasn't returned yet, parse query directly
    if (queryTermsEnriched.length === 0) {
      for (const t of query.trim().split(/\s*,\s*/).filter(Boolean)) {
        addUnique(t);
      }
    }

    // 2. Selected AI suggestions (alphabetically — they come pre-sorted from backend)
    if (useAiSuggestions) {
      for (const sg of suggestionsEnriched) {
        if (selectedSuggestions.has(sg.term)) {
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

    const searchTerms = buildSearchTerms();

    addMessage({ type: 'user', content: query });

    // Snapshot before clearing
    const termsToSend = searchTerms;
    const derivativesWereOn = includeDerivatives;
    setQuery("");
    setQueryTermsEnriched([]);
    setSuggestionsEnriched([]);
    setSelectedSuggestions(new Set());

    try {
      const params = new URLSearchParams({ terms: termsToSend.join(",") });
      const apiUrl = `${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.TESTIMONIES_SEARCH}?${params}`;
      const res = await fetch(apiUrl);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data: TestimoniesSearchResponse = await res.json();

      const searchTermsText = data.searchTerms.join(', ');
      const resultsText = data.results.length > 0
        ? `Found ${data.results.length} testimonies`
        : 'No testimonies found';
      const summaryText = `Search terms: ${searchTermsText}${derivativesWereOn ? ' (+ derivatives)' : ''}\n\n${resultsText}`;

      addMessage({ type: 'assistant', content: summaryText, result: data });
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
                  <Text size="lg" fw="bold" mb="sm">Search Terms</Text>
                  <Group gap="xs" mb="md" style={{ flexWrap: 'wrap' }}>
                    {(message.result as TestimoniesSearchResponse).searchTerms.slice(0, 30).map((term, i) => (
                      <Badge key={i} variant="light" color="blue" size="md">{term}</Badge>
                    ))}
                    {(message.result as TestimoniesSearchResponse).searchTerms.length > 30 && (
                      <Badge variant="light" color="gray" size="md">
                        +{(message.result as TestimoniesSearchResponse).searchTerms.length - 30} more
                      </Badge>
                    )}
                  </Group>
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

  /** Render a single AI suggestion badge with optional derivative sub-badges. */
  function renderSuggestionBadge(sg: EnrichedTerm) {
    const isSelected = selectedSuggestions.has(sg.term);
    return (
      <Box key={sg.term} style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'flex-start', gap: 2 }}>
        <Tooltip label={isSelected ? 'Click to exclude' : 'Click to include'} withArrow>
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
        {/* Show derivatives underneath when both the term is selected and derivatives toggle is on */}
        {isSelected && includeDerivatives && sg.derivatives.length > 0 && (
          <Group gap={3} ml={4} mt={2}>
            {sg.derivatives.slice(0, 6).map(d => (
              <Badge key={d} variant="light" color="grape" size="xs">{d}</Badge>
            ))}
            {sg.derivatives.length > 6 && (
              <Badge variant="light" color="gray" size="xs">+{sg.derivatives.length - 6}</Badge>
            )}
          </Group>
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
        <Group gap="lg" mb={(useAiSuggestions && suggestionsEnriched.length > 0) || (includeDerivatives && queryTermsEnriched.length > 0) ? 'sm' : 0}>
          <Switch
            label="Include word derivatives"
            description="Also match plurals, past tense, etc."
            checked={includeDerivatives}
            onChange={e => setIncludeDerivatives(e.currentTarget.checked)}
            size="sm"
          />
          <Switch
            label="AI suggested terms"
            description="Expand search with related words"
            checked={useAiSuggestions}
            onChange={e => setUseAiSuggestions(e.currentTarget.checked)}
            size="sm"
          />
        </Group>

        {/* User query term derivatives preview (only when derivatives are on and we have data) */}
        {includeDerivatives && queryTermsEnriched.length > 0 && (
          <Box mb={useAiSuggestions && suggestionsEnriched.length > 0 ? 'sm' : 0}>
            <Text size="xs" c="dimmed" mb={4}>Your terms + derivatives:</Text>
            <Group gap={6} style={{ flexWrap: 'wrap' }}>
              {queryTermsEnriched.map(qt => (
                <Group key={qt.term} gap={3} style={{ flexWrap: 'wrap', alignItems: 'center' }}>
                  <Badge variant="filled" color="teal" size="md">{qt.term}</Badge>
                  {qt.derivatives.slice(0, 5).map(d => (
                    <Badge key={d} variant="light" color="teal" size="xs">{d}</Badge>
                  ))}
                  {qt.derivatives.length > 5 && (
                    <Badge variant="light" color="gray" size="xs">+{qt.derivatives.length - 5}</Badge>
                  )}
                </Group>
              ))}
            </Group>
          </Box>
        )}

        {/* AI suggested terms */}
        {useAiSuggestions && query.trim() && (
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
      <Box style={{ maxWidth: '66.67%', margin: '0 auto', height: '60vh', display: 'flex', flexDirection: 'column' }}>
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
