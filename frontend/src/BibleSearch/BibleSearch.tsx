import { useState, useRef, useEffect } from 'react';
import { Text, Box, Button, Loader, Textarea, Paper, Group, Divider, SegmentedControl, Stack, ScrollArea, Collapse } from '@mantine/core';
import { styles } from '../BibleNavigator/BibleNavigator.styles';
import { useBibleChat, ChatMessage } from '../contexts/BibleChatContext';
import { API_CONFIG } from '../config/api';


function findTestamentAndGroup(nkjvData: any, book: string) {
  for (const testament of Object.keys(nkjvData)) {
    for (const group of Object.keys(nkjvData[testament])) {
      if (nkjvData[testament][group][book]) {
        return { testament, group, bookKey: book };
      }
      // Try with 's' appended if not found
      if (nkjvData[testament][group][book + 's']) {
        return { testament, group, bookKey: book + 's' };
      }
    }
  }
  return null;
}

export default function AIBibleSearch() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nkjv, setNKJV] = useState<any>(null);
  const { chatHistory, addMessage, toggleMessageCollapse, clearChat, exportChatHistory } = useBibleChat();
  
  // Debug logging
  console.log('BibleSearch - chatHistory length:', chatHistory.length);
  console.log('BibleSearch - chatHistory:', chatHistory);
  const nkjvLoaded = useRef(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  
  // Search control states
  const [resultCount, setResultCount] = useState("few");
  const [contentType, setContentType] = useState("verses");
  const [modelType, setModelType] = useState("fast");

  // Load NKJV.json only once
  const loadNKJV = async () => {
    if (nkjvLoaded.current) return nkjv;
    const res = await fetch('data/NKJV.json');
    if (!res.ok) throw new Error('Failed to load NKJV.json');
    const data = await res.json();
    setNKJV(data);
    nkjvLoaded.current = true;
    return data;
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    setError(null);
    
    // Add user message to chat history
    addMessage({
      type: 'user',
      content: query
    });
    
    const currentQuery = query;
    const currentSettings = { resultCount, contentType, modelType };
    setQuery(""); // Clear input
    
    try {
      // Load NKJV if not loaded
      if (!nkjvLoaded.current) {
        const nkjvData = await loadNKJV();
        setNKJV(nkjvData);
      }
      
      // Build search parameters
      const params = new URLSearchParams({
        query: currentQuery,
        result_count: resultCount,
        content_type: contentType,
        model_type: modelType
      });
      
      const apiUrl = `${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.SEARCH}?${params.toString()}`;
      console.log('Making API request to:', apiUrl);
      
      const res = await fetch(apiUrl);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      
      // Create summary text with actual verse references
      const passageRefs = data.passages?.map((passage: any) => passageReferenceString(passage)) || [];
      const bonusRefs = data.secondary_passages?.map((passage: any) => passageReferenceString(passage)) || [];
      
      let summaryText = '';
      if (passageRefs.length > 0) {
        summaryText = passageRefs.join(', ');
        if (bonusRefs.length > 0) {
          summaryText += ` (${bonusRefs.length} bonus: ${bonusRefs.join(', ')})`;
        }
      } else {
        summaryText = 'No passages found';
      }
      
      // Add assistant response to chat history
      addMessage({
        type: 'assistant',
        content: summaryText,
        result: data,
        settings: currentSettings
      });
      
      // Clear any previous errors on successful search
      setError(null);
    } catch (err: any) {
      const errorMessage = err.message || 'Unknown error';
      setError(errorMessage);
      
      // Add error message to chat history
      addMessage({
        type: 'assistant',
        content: `Error: ${errorMessage}`,
        settings: currentSettings
      });
    } finally {
      setLoading(false);
    }
  };

  // Helper to get all verses in a passage object (may span chapters)
  function getNKJVTextForPassage(nkjv: any, passage: any): string | null {
    if (!nkjv || !passage || !passage.book) return null;
    const book = passage.book;
    const found = findTestamentAndGroup(nkjv, book);
    if (!found) return null;
    const { testament, group, bookKey } = found;
    if (!testament || !group || !bookKey) return null;
    const bookData = nkjv[testament]?.[group]?.[bookKey];
    if (!bookData) return null;

    // Single verse
    if (passage.chapter && passage.verse) {
      const chapterStr = String(passage.chapter);
      const verseStr = String(passage.verse);
      return bookData[chapterStr]?.[verseStr] || null;
    }

    // Range (may span chapters)
    const startChapter = passage.start_chapter;
    const startVerse = passage.start_verse;
    const endChapter = passage.end_chapter;
    const endVerse = passage.end_verse;
    if (
      startChapter === undefined || startVerse === undefined ||
      endChapter === undefined || endVerse === undefined
    ) return null;

    const texts: string[] = [];
    for (let ch = startChapter; ch <= endChapter; ch++) {
      const chapterStr = String(ch);
      const versesObj = bookData[chapterStr];
      if (!versesObj) continue;
      let verseStart = ch === startChapter ? startVerse : 1;
      let verseEnd = ch === endChapter ? endVerse : Math.max(...Object.keys(versesObj).map(Number));
      for (let v = verseStart; v <= verseEnd; v++) {
        const verseStr = String(v);
        const text = versesObj[verseStr];
        if (text) texts.push(text);
      }
    }
    return texts.length > 0 ? texts.join(' ') : null;
  }

  // Helper to render passage reference as a string
  function passageReferenceString(passage: any): string {
    if (passage.chapter && passage.verse) {
      return `${passage.book} ${passage.chapter}:${passage.verse}`;
    }
    if (
      passage.start_chapter !== undefined && passage.start_verse !== undefined &&
      passage.end_chapter !== undefined && passage.end_verse !== undefined
    ) {
      if (passage.start_chapter === passage.end_chapter) {
        return `${passage.book} ${passage.start_chapter}:${passage.start_verse}-${passage.end_verse}`;
      } else {
        return `${passage.book} ${passage.start_chapter}:${passage.start_verse} - ${passage.end_chapter}:${passage.end_verse}`;
      }
    }
    return passage.book;
  }

  // Auto-scroll to bottom when new messages are added
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [chatHistory]);

  // Render a list of passage objects with their NKJV text
  function renderPassages(passages: any[] | undefined, isCollapsed: boolean = false) {
    if (!passages || passages.length === 0) return <Text>No passages found.</Text>;
    
    if (isCollapsed) {
      return <Text size="sm" c="dimmed">{passages.length} passages found</Text>;
    }
    
    return (
      <>
        {passages.map((passage, idx) => {
          const text = getNKJVTextForPassage(nkjv, passage);
          return (
            <Paper key={JSON.stringify(passage) + idx} shadow="xs" p="sm" mb="sm" radius="md" withBorder>
              <Text size="md" fw="bold">{passageReferenceString(passage)}</Text>
              <Divider my="xs" />
              <Text size="md" color={text ? undefined : 'red'}>
                {text || 'Not found in NKJV data.'}
              </Text>
            </Paper>
          );
        })}
      </>
    );
  }

  // Render bonus passages with proper messaging
  function renderBonusPassages(passages: any[] | undefined, isCollapsed: boolean = false) {
    if (!passages || passages.length === 0) {
      return <Text size="sm" c="dimmed">No bonus passages.</Text>;
    }
    
    if (isCollapsed) {
      return <Text size="sm" c="dimmed">{passages.length} bonus passages found.</Text>;
    }
    
    return (
      <>
        <Text size="sm" c="dimmed" mb="sm">{passages.length} bonus passages found.</Text>
        {passages.map((passage, idx) => {
          const text = getNKJVTextForPassage(nkjv, passage);
          return (
            <Paper key={JSON.stringify(passage) + idx} shadow="xs" p="sm" mb="sm" radius="md" withBorder>
              <Text size="md" fw="bold">{passageReferenceString(passage)}</Text>
              <Divider my="xs" />
              <Text size="md" color={text ? undefined : 'red'}>
                {text || 'Not found in NKJV data.'}
              </Text>
            </Paper>
          );
        })}
      </>
    );
  }

  // Format timestamp to nearest minute
  function formatTimestamp(date: Date): string {
    const roundedDate = new Date(date);
    roundedDate.setSeconds(0, 0); // Round to nearest minute
    return roundedDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  // Format settings for display
  function formatSettings(settings: any): string {
    if (!settings) return '';
    const resultCountLabel = settings.resultCount === 'one' ? 'One' : 
                            settings.resultCount === 'few' ? 'Few' : 'Many';
    const contentTypeLabel = settings.contentType === 'verses' ? 'Verses' :
                            settings.contentType === 'passages' ? 'Passages' : 'All';
    const modelTypeLabel = settings.modelType === 'fast' ? 'Fast' : 'Advanced';
    
    return `Settings: ${resultCountLabel} results, ${contentTypeLabel}, ${modelTypeLabel} model`;
  }

  // Render a chat message
  function renderChatMessage(message: ChatMessage) {
    const isCollapsed = message.collapsed || false;
    
    return (
      <Box key={message.id} mb="md">
        <Paper 
          shadow="xs" 
          p="md" 
          radius="md" 
          withBorder
          style={{
            backgroundColor: message.type === 'user' ? '#f8f9fa' : '#ffffff',
            marginLeft: message.type === 'user' ? '20%' : '0',
            marginRight: message.type === 'user' ? '0' : '20%'
          }}
        >
          <Group justify="space-between" mb="xs">
            <Text size="sm" fw={500} c={message.type === 'user' ? 'blue' : 'green'}>
              {message.type === 'user' ? 'You' : 'AI Assistant'}
            </Text>
            <Text size="xs" c="dimmed">
              {formatTimestamp(message.timestamp)}
            </Text>
          </Group>
          
          <Text size="md" mb={message.result ? "sm" : 0}>
            {message.content}
          </Text>
          
          {message.result && (
            <Box>
              <Button
                variant="subtle"
                size="xs"
                onClick={() => toggleMessageCollapse(message.id)}
                mb="sm"
              >
                {isCollapsed ? 'Show' : 'Hide'} Results
              </Button>
              
              <Collapse in={!isCollapsed}>
                <Box>
                  <Text size="lg" fw="bold" mb="sm">Passages</Text>
                  <Box style={styles.verseDisplay} mb="md">
                    {renderPassages(message.result.passages, isCollapsed)}
                  </Box>
                  
                  <Text size="lg" fw="bold" mb="sm">Bonus Passages</Text>
                  <Box style={styles.verseDisplay} mb="sm">
                    {renderBonusPassages(message.result.secondary_passages, isCollapsed)}
                  </Box>
                  
                  {/* Settings footer */}
                  {message.settings && (
                    <Text size="xs" c="dimmed" style={{ fontStyle: 'italic' }}>
                      {formatSettings(message.settings)}
                    </Text>
                  )}
                </Box>
              </Collapse>
            </Box>
          )}
        </Paper>
      </Box>
    );
  }

  return (
    <Box style={styles.container}>
      <Text size="xl" fw="bold" mb="md">AI Bible Search</Text>
      
      {/* Search Settings - Moved to top */}
      <Paper shadow="xs" p="md" mb="md" radius="md" withBorder>
        <Group justify="space-between" mb="sm">
          <Text size="md" fw="bold">Search Settings</Text>
          {chatHistory.length > 0 && (
            <Group gap="xs">
              <Button 
                variant="outline" 
                size="xs" 
                color="blue"
                onClick={exportChatHistory}
              >
                Export Chat
              </Button>
              <Button 
                variant="outline" 
                size="xs" 
                color="red"
                onClick={clearChat}
              >
                Clear Chat History
              </Button>
            </Group>
          )}
        </Group>
        <Group gap="lg" align="flex-start">
          <Box>
            <Text size="sm" fw={500} mb={3}>
              Result Count
            </Text>
            <SegmentedControl
              value={resultCount}
              onChange={setResultCount}
              data={[
                { label: 'One', value: 'one' },
                { label: 'Few', value: 'few' },
                { label: 'Many', value: 'many' },
              ]}
              size="sm"
            />
          </Box>
          
          <Box>
            <Text size="sm" fw={500} mb={3}>
              Content Type
            </Text>
            <SegmentedControl
              value={contentType}
              onChange={setContentType}
              data={[
                { label: 'Verses', value: 'verses' },
                { label: 'Passages', value: 'passages' },
                { label: 'All', value: 'all' },
              ]}
              size="sm"
            />
          </Box>
          
          <Box>
            <Text size="sm" fw={500} mb={3}>
              Model Type
            </Text>
            <SegmentedControl
              value={modelType}
              onChange={setModelType}
              data={[
                { label: 'Fast', value: 'fast' },
                { label: 'Advanced', value: 'advanced' },
              ]}
              size="sm"
            />
          </Box>
        </Group>
      </Paper>
      
      {/* Chat Interface */}
      <Box style={{ 
        maxWidth: '66.67%', 
        margin: '0 auto',
        height: '60vh', 
        display: 'flex', 
        flexDirection: 'column' 
      }}>
        {chatHistory.length === 0 ? (
          /* Empty State - Input is more prominent */
          <Stack gap="lg" style={{ flex: 1, justifyContent: 'center' }}>
            <Paper shadow="xs" p="xl" radius="md" withBorder style={{ textAlign: 'center' }}>
              <Text size="lg" c="dimmed">
                Start a conversation with the AI Bible Search
              </Text>
              <Text size="sm" c="dimmed" mt="xs">
                Ask questions about Bible verses, stories, or themes
              </Text>
            </Paper>
            
            {/* Prominent Input for Empty State */}
            <Paper shadow="md" p="lg" radius="md" withBorder>
              <Group align="flex-end">
                <Textarea
                  value={query}
                  onChange={e => setQuery(e.currentTarget.value)}
                  placeholder="Ask me anything about the Bible..."
                  style={{ flex: 1 }}
                  styles={styles.autocomp}
                  onKeyDown={e => { 
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSearch();
                    }
                  }}
                  minRows={2}
                  maxRows={4}
                  size="lg"
                />
                <Button 
                  onClick={handleSearch} 
                  loading={loading} 
                  disabled={!query.trim()} 
                  color="blue" 
                  size="lg"
                >
                  Send
                </Button>
              </Group>
            </Paper>
          </Stack>
        ) : (
          /* Chat History Exists - Normal Layout */
          <>
            {/* Chat History */}
            <ScrollArea 
              ref={scrollAreaRef}
              style={{ flex: 1, marginBottom: '1rem' }}
              scrollbarSize={6}
            >
              {chatHistory.map((message) => 
                renderChatMessage(message)
              )}
              
          {loading && (
            <Box mb="md">
              <Paper shadow="xs" p="md" radius="md" withBorder style={{ marginRight: '20%' }}>
                <Group>
                  <Loader size="sm" color="blue" />
                  <Text size="sm" c="dimmed">AI is searching...</Text>
                </Group>
              </Paper>
            </Box>
          )}
          
          {error && (
            <Box mb="md">
              <Paper shadow="xs" p="md" radius="md" withBorder style={{ marginRight: '20%', backgroundColor: '#ffe6e6' }}>
                <Group>
                  <Text size="sm" c="red" fw={500}>Error: {error}</Text>
                  <Button 
                    variant="subtle" 
                    size="xs" 
                    color="red"
                    onClick={() => setError(null)}
                  >
                    Dismiss
                  </Button>
                </Group>
              </Paper>
            </Box>
          )}
            </ScrollArea>
            
            {/* Chat Input */}
            <Paper shadow="xs" p="md" radius="md" withBorder>
              <Group align="flex-end">
                <Textarea
                  value={query}
                  onChange={e => setQuery(e.currentTarget.value)}
                  placeholder="Ask me anything about the Bible..."
                  style={{ flex: 1 }}
                  styles={styles.autocomp}
                  onKeyDown={e => { 
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSearch();
                    }
                  }}
                  minRows={1}
                  maxRows={4}
                />
                <Button 
                  onClick={handleSearch} 
                  loading={loading} 
                  disabled={!query.trim()} 
                  color="blue" 
                  size="md"
                >
                  Send
                </Button>
              </Group>
            </Paper>
          </>
        )}
      </Box>
    </Box>
  );
}