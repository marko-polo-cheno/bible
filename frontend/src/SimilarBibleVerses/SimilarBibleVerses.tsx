import { useState, useEffect } from 'react';
import { Radio, Text, Box, Autocomplete, Button } from '@mantine/core';
import { styles } from '../BibleNavigator/BibleNavigator.styles';

const verbose = true; // Set to true to enable debugging logs

interface BibleData {
  [testament: string]: {
    [group: string]: {
      [book: string]: {
        [chapter: string]: { [verse: string]: string };
      };
    };
  };
}

interface NearestNeighbors {
  [book: string]: {
    [chapter: string]: {
      [verse: string]: string[];
    };
  };
}

export function SimilarBibleVerses() {
  const [bibleVersions, setBibleVersions] = useState<{ [version: string]: BibleData }>({});
  const [nearestNeighbors, setNearestNeighbors] = useState<NearestNeighbors>({});
  const [testament, setTestament] = useState<string>("new");
  const [book, setBook] = useState<string>("John");
  const [chapter, setChapter] = useState<string>("3");
  const [verse, setVerse] = useState<string>("16");
  const [neighbors, setNeighbors] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      try {
        // Load Bible versions
        const versions = ['pinyin', 'chinese', 'NKJV'];
        const loadedVersions: [string, BibleData][] = await Promise.all(
          versions.map(async (version) => {
            const response = await fetch(`data/${version}.json`);
            if (!response.ok) {
              throw new Error(`HTTP error! Status: ${response.status} for ${version}`);
            }
            return [version, await response.json()];
          })
        );

        const orderedVersions = Object.fromEntries(loadedVersions);
        setBibleVersions(orderedVersions);

        // Load nearest neighbors data
        const nnResponse = await fetch('data/nn.json');
        if (!nnResponse.ok) {
          throw new Error(`HTTP error! Status: ${nnResponse.status} for nearest neighbors`);
        }
        const nnData = await nnResponse.json();
        setNearestNeighbors(nnData);
        
        if (verbose) console.log('Loaded Bible versions and nearest neighbors data');
      } catch (error) {
        console.error('Error loading data:', error);
        alert('Failed to load Bible data or nearest neighbors. Please ensure all files are located in public/data.');
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, []);

  // Parse a verse reference like "Genesis 1:1" into { book: "Genesis", chapter: "1", verse: "1" }
  const parseVerseReference = (reference: string) => {
    const match = reference.match(/^(.+) (\d+):(\d+)$/);
    if (match) {
      return {
        book: match[1],
        chapter: match[2],
        verse: match[3]
      };
    }
    return null;
  };

  // Get available verses for the selected book and chapter
  const getAvailableVerses = (data: any) => {
    if (!testament || !book || !chapter) return [];
    if (verbose) console.log('Getting available verses');
    const verses = new Set<number>();

    // Iterate through groups to extract verses
    Object.keys(data[testament] || {}).forEach((group) => {
      const chapterData = data[testament]?.[group]?.[book]?.[chapter] ?? {};
      
      Object.keys(chapterData).forEach((verse) => {
        verses.add(parseInt(verse, 10));
      });
    });

    const sortedVerses = Array.from(verses).sort((a, b) => a - b);
    if (verbose) console.log('Available verses:', sortedVerses);
    return sortedVerses;
  };

  // Handle button click to find nearest neighbors
  const handleFindNeighbors = () => {
    if (!book || !chapter || !verse) {
      alert('Please select a book, chapter, and verse.');
      return;
    }

    // Get nearest neighbors for the selected verse
    const nnList = nearestNeighbors?.[book]?.[chapter]?.[verse] || [];
    
    // Create a list with the current verse at the top, followed by neighbors
    const allVerses = [`${book} ${chapter}:${verse}`, ...nnList];
    
    setNeighbors(allVerses);
    
    if (verbose) console.log('Found neighbors:', allVerses);
  };

  // Display the main verse and its neighbors
  const displayVerseAndNeighbors = () => {
    if (neighbors.length === 0) {
      return 'Click "Find Nearest Neighbors" to display verses.';
    }

    const colors = ['#FFFFE0', '#E0FFFF', '#FFE0E0']; // Light yellow, blue, pink
    const verses: string[] = [];

    // Process each verse reference
    neighbors.forEach((reference, index) => {
      const parsed = parseVerseReference(reference);
      if (!parsed) {
        verses.push(`<p>Invalid reference: ${reference}</p>`);
        return;
      }

      const { book: vBook, chapter: vChapter, verse: vVerse } = parsed;
      const verseContent: { [version: string]: string } = {};

      // Get verse content from all available Bible versions
      Object.entries(bibleVersions).forEach(([version, data]) => {
        try {
          // Find testament for this book
          if (!vBook) {
            console.error(`Invalid book name: ${vBook}`);
            return;
          }
          if (!vChapter) {
            console.error(`Invalid chapter name: ${vBook}`);
            return;
          }
          if (!vVerse) {
            console.error(`Invalid verse name: ${vBook}`);
            return;
          }
          const testamentForBook = findTestamentForBook(data, vBook);
          if (!testamentForBook) return;

          // Find the verse in the Bible data
          Object.keys(data[testamentForBook] || {}).forEach((group) => {
            const chapterData = testamentForBook ? data[testamentForBook]?.[group]?.[vBook]?.[vChapter] ?? {} : {};
            if (chapterData[vVerse]) {
              verseContent[version] = chapterData[vVerse] as string;
            }
          });
        } catch (error) {
          console.error(`Error displaying verse for ${version}:`, error);
        }
      });

      // Special styling for the main verse (index 0)
      const isMainVerse = index === 0;
      const headerBg = isMainVerse ? '#FFD700' : '#F0F0F0'; // Gold for main verse, light gray for neighbors

      verses.push(`<div style="margin: 10px 0; padding: 5px; border-radius: 4px; ${isMainVerse ? 'border: 2px solid #FFD700;' : ''}">`);
      verses.push(`<p style="background-color: ${headerBg}; padding: 5px; border-radius: 4px; margin: 0 0 5px 0; font-weight: bold;">${isMainVerse ? 'MAIN VERSE' : `NEIGHBOR ${index}`}: ${reference}</p>`);

      if (Object.keys(verseContent).length > 0) {
        Object.entries(verseContent).forEach(([version, content], vIndex) => {
          const color = colors[vIndex % colors.length]; // Assign a color cyclically
          verses.push(
            `<p style="background-color: ${color}; padding: 5px; border-radius: 4px; margin: 2px 0;"><strong>${version}:</strong> ${content}</p>`
          );
        });
      } else {
        verses.push(`<p style="padding: 5px;">No content available for this verse.</p>`);
      }

      verses.push('</div>');
    });

    // Wrap the verses in a container for rendering as HTML
    return verses.join('\n');
  };

  // Helper function to find which testament contains a specific book
  const findTestamentForBook = (data: BibleData, bookName: string): string | null => {
    for (const testamentName of ['old', 'new']) {
      for (const groupName in data[testamentName] || {}) {
        if (data[testamentName]?.[groupName]?.[bookName]) {
          return testamentName;
        }
      }
    }
    return null;
  };

  if (isLoading) {
    return <Text>Loading Bible data...</Text>;
  }

  const firstVersion = Object.values(bibleVersions)[2]; // Using NKJV as reference

  return (
    <div style={styles.container}>
      <Text size="xl" fw="bold" mb="md">Bible Nearest Neighbors Explorer</Text>
      
      <Text>Select a Testament:</Text>
      <div style={styles.flexContainer}>
        <Radio.Group value={testament} onChange={setTestament}>
          {['old', 'new'].map((item) => (
            <Radio
              value={item}
              label={item === 'old' ? 'Old Testament' : 'New Testament'}
              key={item}
              styles={{
                root: styles.radioRoot,
                inner: styles.radioInner,
                label: styles.getRadioLabel(testament === item)
              }}
            />
          ))}
        </Radio.Group>
      </div> 

      {testament && (
        <Autocomplete
          label="Select a Book:"
          placeholder="Select a book"
          value={book}
          onChange={(value) => setBook(value ?? '')}
          data={
            firstVersion && testament
              ? Object.entries(firstVersion[testament] || {}).map(([groupName, groupBooks]) => ({
                group: groupName,
                items: Object.keys(groupBooks),
              }))
              : []
          }
          maxDropdownHeight={250}
          styles={styles.autocomp}
        />
      )}

      {book && (
        <Autocomplete
          label="Select a Chapter:"
          placeholder="Pick or type a chapter"
          value={chapter}
          onChange={(value) => {
            setChapter(value ?? '');
            setVerse(''); // Reset verse when chapter changes
          }}
          data={
            firstVersion && testament && book
              ? Object.entries(firstVersion[testament] || {})
                .flatMap(([_, groupBooks]) =>
                  Object.keys(groupBooks?.[book] || {})
                )
              : []
          }
          styles={styles.autocomp}
          maxDropdownHeight={250}
        />
      )}

      {chapter && (
        <Autocomplete
          label="Select a Verse:"
          placeholder="Pick or type a verse number"
          value={verse}
          onChange={(value) => setVerse(value ?? '')}
          data={
            getAvailableVerses(firstVersion).map(String)
          }
          styles={styles.autocomp}
          maxDropdownHeight={250}
        />
      )}

      {verse && (
        <Button 
          mt="md" 
          mb="md" 
          onClick={handleFindNeighbors}
          color="blue"
          size="md"
          fullWidth
        >
          Find Nearest Neighbors
        </Button>
      )}

      {neighbors.length > 0 && (
        <Box mt="md">
          <Text size="lg" fw="bold">
            {book} {chapter}:{verse} and its Nearest Neighbors
          </Text>
          <div style={styles.verseDisplay} dangerouslySetInnerHTML={{ __html: displayVerseAndNeighbors() }} />
        </Box>
      )}
    </div>
  );
}