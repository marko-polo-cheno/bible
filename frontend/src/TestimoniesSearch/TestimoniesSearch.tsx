import { useState, useRef, useEffect } from 'react';
import { Text, Box, Button, Loader, Textarea, Paper, Group, ScrollArea, Collapse, Stack } from '@mantine/core';
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

export default function TestimoniesSearch() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { chatHistory, addMessage, toggleMessageCollapse, clearChat, exportChatHistory } = useTestimoniesChat();
  const scrollAreaRef = useRef<HTMLDivElement>(null);

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
    setQuery(""); // Clear input
    
    try {
      const params = new URLSearchParams({
        query: currentQuery
      });
      
      const apiUrl = `${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.TESTIMONIES_SEARCH}?${params.toString()}`;
      console.log('Making API request to:', apiUrl);
      
      const res = await fetch(apiUrl);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data: TestimoniesSearchResponse = await res.json();
      
      // Create summary text with search terms and results
      const searchTermsText = data.searchTerms.join(', ');
      const resultsText = data.results.length > 0 
        ? `Found ${data.results.length} testimonies with ${data.results.slice(0, 10).map(r => `${r.filename} (${r.hitCount} hits)`).join(', ')}`
        : 'No testimonies found';
      
      const summaryText = `Search terms: ${searchTermsText}\n\n${resultsText}`;
      
      // Add assistant response to chat history
      addMessage({
        type: 'assistant',
        content: summaryText,
        result: data
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
      });
    } finally {
      setLoading(false);
    }
  };

  // Auto-scroll to bottom when new messages are added
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [chatHistory]);

  // Format timestamp to nearest minute
  function formatTimestamp(date: Date): string {
    const roundedDate = new Date(date);
    roundedDate.setSeconds(0, 0); // Round to nearest minute
    return roundedDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  // Render testimonies results
  function renderTestimoniesResults(results: TestimonyResult[] | undefined, isCollapsed: boolean = false) {
    if (!results || results.length === 0) return <Text>No testimonies found.</Text>;
    
    if (isCollapsed) {
      return <Text size="sm" c="dimmed">{results.length} testimonies found</Text>;
    }
    
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
                  <Text size="lg" fw="bold" mb="sm">Search Terms</Text>
                  <Text size="md" mb="md" c="blue">
                    {(message.result as TestimoniesSearchResponse).searchTerms.join(', ')}
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

  return (
    <Box style={styles.container}>
      <Text size="xl" fw="bold" mb="md">Testimonies Search</Text>
      
      {/* Search Settings */}
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
        <Text size="sm" c="dimmed">
          Search through testimonies using AI-powered term expansion and content matching
        </Text>
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
                Search through testimonies
              </Text>
              <Text size="sm" c="dimmed" mt="xs">
                Enter a term or topic to find relevant testimonies
              </Text>
            </Paper>
            
            {/* Prominent Input for Empty State */}
            <Paper shadow="md" p="lg" radius="md" withBorder>
              <Group align="flex-end">
                <Textarea
                  value={query}
                  onChange={e => setQuery(e.currentTarget.value)}
                  placeholder="Enter a term or topic (e.g., 'leukemia', 'faith', 'healing')..."
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
                  Search
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
                  <Text size="sm" c="dimmed">AI is searching testimonies...</Text>
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
                  placeholder="Enter a term or topic to search testimonies..."
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
                  Search
                </Button>
              </Group>
            </Paper>
          </>
        )}
      </Box>
    </Box>
  );
}
