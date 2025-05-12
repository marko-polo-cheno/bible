import { useState } from 'react';
import { Text, Box, Button, Loader, TextInput, Paper, Group } from '@mantine/core';
import { styles } from '../BibleNavigator/BibleNavigator.styles';

export default function AIBibleSearch() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      console.log('Sending fetch to /api/search with query:', query);
      const res0 = await fetch(
        `https://bible-search-wheat.vercel.app/api/search?query=${encodeURIComponent(query)}`
      );
      console.log('Sending fetch to /search with query:', query);
      const res = await fetch(
        `https://bible-search-wheat.vercel.app/search?query=${encodeURIComponent(query)}`
      );
      console.log('Fetch response:', res);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      console.log('Fetch response JSON:', data);
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Unknown error');
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box style={styles.container}>
      <Text size="xl" fw="bold" mb="md">AI Bible Search</Text>
      <Group align="flex-end" mb="md">
        <TextInput
          value={query}
          onChange={e => setQuery(e.currentTarget.value)}
          placeholder="What are you looking for from the Bible?"
          style={{ minWidth: 300 }}
          styles={styles.autocomp}
          label="Search Query"
          onKeyDown={e => { if (e.key === 'Enter') handleSearch(); }}
        />
        <Button onClick={handleSearch} loading={loading} disabled={!query.trim()} color="blue" size="md">
          Search
        </Button>
      </Group>
      {loading && <Loader color="blue" />}
      {error && <Text color="red" mt="md">{error}</Text>}
      {result && (
        <Paper shadow="xs" p="md" mt="md" radius="md" withBorder>
          <Text size="lg" fw="bold" mb="sm">Passages</Text>
          <Box style={styles.verseDisplay} mb="md">
            <pre style={{ margin: 0 }}>{JSON.stringify(result.passages, null, 2)}</pre>
          </Box>
          <Text size="lg" fw="bold" mb="sm">Secondary Passages</Text>
          <Box style={styles.verseDisplay}>
            <pre style={{ margin: 0 }}>{JSON.stringify(result.secondary_passages, null, 2)}</pre>
          </Box>
        </Paper>
      )}
    </Box>
  );
}