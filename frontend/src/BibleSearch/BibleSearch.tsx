import { useState, useRef } from 'react';
import { Text, Box, Button, Loader, TextInput, Paper, Group, Divider } from '@mantine/core';
import { styles } from '../BibleNavigator/BibleNavigator.styles';


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
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nkjv, setNKJV] = useState<any>(null);
  const nkjvLoaded = useRef(false);

  // Load NKJV.json only once
  const loadNKJV = async () => {
    if (nkjvLoaded.current) return;
    const res = await fetch('data/NKJV.json');
    if (!res.ok) throw new Error('Failed to load NKJV.json');
    const data = await res.json();
    setNKJV(data);
    nkjvLoaded.current = true;
    return data;
  };

  const handleSearch = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      // Load NKJV if not loaded
      if (!nkjvLoaded.current) {
        await loadNKJV();
      }
      const res = await fetch(
        `https://bible-production-d7b3.up.railway.app/search?query=${encodeURIComponent(query)}`
      );
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Unknown error');
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

  // Render a list of passage objects with their NKJV text
  function renderPassages(passages: any[] | undefined) {
    if (!passages || passages.length === 0) return <Text>No passages found.</Text>;
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
            {renderPassages(result.passages)}
          </Box>
          <Text size="lg" fw="bold" mb="sm">Bonus Passages</Text>
          <Box style={styles.verseDisplay}>
            {renderPassages(result.secondary_passages)}
          </Box>
        </Paper>
      )}
    </Box>
  );
}