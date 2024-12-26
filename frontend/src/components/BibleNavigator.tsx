import { useState, useEffect } from 'react';
import { Radio, Text, Box } from '@mantine/core';

const verbose = true; // Set to true to enable debugging logs

interface BibleData {
  [testament: string]: {
    [group: string]: {
      [book: string]: {
        [chapter: string]: { [verse: string]: string }; // Chapter is now an object with verse mappings
      };
    };
  };
}

export function BibleNavigator() {
  const [bibleVersions, setBibleVersions] = useState<{ [version: string]: BibleData }>({});
  const [testament, setTestament] = useState<string | null>(null);
  const [book, setBook] = useState<string | null>(null);
  const [chapter, setChapter] = useState<string | null>(null);
  const [verseRange, setVerseRange] = useState<string | null>(null);

  useEffect(() => {
    const loadBibleVersions = async () => {
      try {
        const versions = ['NKJV', 'chinese', 'pinyin'];
        const loadedVersions: { [version: string]: BibleData } = {};

        await Promise.all(
          versions.map(async (version) => {
            const response = await fetch(`data/${version}.json`);
            if (!response.ok) {
              throw new Error(`HTTP error! Status: ${response.status} for ${version}`);
            }
            loadedVersions[version] = await response.json();
          })
        );

        setBibleVersions(loadedVersions);
      } catch (error) {
        console.error('Error loading Bible versions:', error);
        alert('Failed to load Bible data. Please ensure all version files are located in public/data.');
      }
    };

    loadBibleVersions();
  }, []);

  const getAvailableVerses = (data: any) => {
    if (!testament || !book || !chapter) return [];
    if (verbose) console.log('Available any:', data); // entire bible in json
    const verses = new Set<number>();

    // Iterate through groups to extract verses
    Object.keys(data[testament] || {}).forEach((group) => {
      if (verbose) console.log(`Group: ${group}`); // Debug the group
      const chapterData = data[testament]?.[group]?.[book]?.[chapter] ?? {};
      if (verbose) console.log('Chapter data:', chapterData); // Debug the chapter data

      Object.keys(chapterData).forEach((verse) => {
        verses.add(parseInt(verse, 10));
      });
    });

    if (verbose) console.log('Available set:', verses); // Debug the set of verses

    const sortedVerses = Array.from(verses).sort((a, b) => a - b);
    if (verbose) console.log('Available verses:', sortedVerses);
    return sortedVerses;
  };

  const generateVerseRanges = (verses: number[]): string[] => {
    if (verses.length === 0) return [];

    const ranges: string[] = [];
    const totalVerses = verses.length;

    let chunkSize: number;
    if (totalVerses <= 10) {
      chunkSize = totalVerses;
    } else if (totalVerses <= 50) {
      chunkSize = Math.ceil(totalVerses / 3);
    } else if (totalVerses <= 100) {
      chunkSize = Math.ceil(totalVerses / 5);
    } else {
      chunkSize = Math.ceil(totalVerses / 6);
    }

    for (let i = 0; i < totalVerses; i += chunkSize) {
      const start = verses[i];
      const end = verses[Math.min(i + chunkSize - 1, totalVerses - 1)];
      ranges.push(`${start}-${end}`);
    }

    if (verbose) console.log('Generated verse ranges:', ranges);
    return ranges;
  };

  const displayVerses = (range: string | null) => {
    if (!testament || !book || !chapter || !range) {
      return 'Please select all options to view verses.';
    }

    const [start, end] = range.split('-').map(Number);
    if (start === undefined || end === undefined || isNaN(start) || isNaN(end)) {
      return 'Invalid verse range selected.';
    }
    const verses: string[] = [];

    for (let verseNum = start; verseNum <= end; verseNum++) {
      const verseContent: { [version: string]: string } = {};

      Object.entries(bibleVersions).forEach(([version, data]) => {
        try {
          Object.keys(data[testament] || {}).forEach((group) => {
            const chapterData = data[testament]?.[group]?.[book]?.[chapter] ?? {};
            if (chapterData[verseNum]) {
              if (chapterData[verseNum]) {
                verseContent[version] = chapterData[verseNum] as string;
              }
            }
          });
        } catch (error) {
          console.error(`Error displaying verse for ${version}:`, error);
        }
      });

      if (Object.keys(verseContent).length > 0) {
        verses.push(`Verse ${verseNum}:`);
        Object.entries(verseContent).forEach(([version, content]) => {
          verses.push(`${version}: ${content}`);
        });
        verses.push('');
      }
    }

    if (verbose) console.log('Displayed verses for range:', range, verses);
    return verses.join('\n');
  };

  if (Object.keys(bibleVersions).length === 0) {
    return <Text>Loading Bible versions...</Text>;
  }

  const firstVersion = Object.values(bibleVersions)[0];

  return (
    <div style={{ padding: '20px' }}>
      <Text>Select a Testament:</Text>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'flex-start' }}>
        <Radio.Group value={testament} onChange={setTestament}>
          {['old', 'new'].map((item) => (
            <Radio
              value={item}
              label={item === 'old' ? 'Old Testament' : 'New Testament'}
              key={item}
              styles={{
                root: {
                  display: 'inline-flex',
                  alignItems: 'center',
                  cursor: 'pointer',
                },
                inner: { display: 'none' },
                label: {
                  backgroundColor: testament === item ? '#d3d3d3' : '#f5f5f5',
                  padding: '8px 12px',
                  borderRadius: '4px',
                  border: `1px solid ${testament === item ? '#888' : '#ccc'}`,
                  cursor: 'pointer',
                  transition: 'background-color 0.2s ease, border-color 0.2s ease',
                  display: 'inline-block',
                  whiteSpace: 'nowrap',
                },
              }}
            />
          ))}
        </Radio.Group>
      </div>

      {testament && (
        <>
          <Text mt="md">Select a Book:</Text>
          {firstVersion && Object.entries(firstVersion[testament] || {}).map(([groupName, groupBooks]) => (
            <div key={groupName}>
              <Text size="sm" fw={500} mt="md">
                {groupName}
              </Text>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'flex-start' }}>
                <Radio.Group value={book} onChange={setBook}>
                  {Object.keys(groupBooks).map((item) => (
                    <Radio
                      value={item}
                      label={item}
                      key={item}
                      styles={{
                        root: {
                          display: 'inline-flex',
                          alignItems: 'center',
                          cursor: 'pointer',
                        },
                        inner: { display: 'none' },
                        label: {
                          backgroundColor: book === item ? '#d3d3d3' : '#f5f5f5',
                          padding: '8px 12px',
                          borderRadius: '4px',
                          border: `1px solid ${book === item ? '#888' : '#ccc'}`,
                          cursor: 'pointer',
                          transition: 'background-color 0.2s ease, border-color 0.2s ease',
                          display: 'inline-block',
                          whiteSpace: 'nowrap',
                        },
                      }}
                    />
                  ))}
                </Radio.Group>
              </div>
            </div>
          ))}
        </>
      )}

      {book && (
        <>
          <Text mt="md">Select a Chapter:</Text>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'flex-start' }}>
            <Radio.Group value={chapter} onChange={setChapter}>
              {firstVersion && testament && firstVersion[testament] && Object.keys(firstVersion[testament])
                .flatMap((group) => Object.keys(firstVersion[testament]?.[group]?.[book] || {}))
                .map((item) => (
                  <Radio
                    value={item}
                    label={item}
                    key={item}
                    styles={{
                      root: {
                        display: 'inline-flex',
                        alignItems: 'center',
                        cursor: 'pointer',
                      },
                      inner: { display: 'none' },
                      label: {
                        backgroundColor: chapter === item ? '#d3d3d3' : '#f5f5f5',
                        padding: '8px 12px',
                        borderRadius: '4px',
                        border: `1px solid ${chapter === item ? '#888' : '#ccc'}`,
                        cursor: 'pointer',
                        transition: 'background-color 0.2s ease, border-color 0.2s ease',
                        display: 'inline-block',
                        whiteSpace: 'nowrap',
                      },
                    }}
                  />
                ))}
            </Radio.Group>
          </div>
        </>
      )}

      {chapter && (
        <>
          <Text mt="md">Select a Verse Range:</Text>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'flex-start' }}>
            <Radio.Group value={verseRange} onChange={setVerseRange}>
              {generateVerseRanges(getAvailableVerses(firstVersion)).map((range) => (
                <Radio
                  value={range}
                  label={range}
                  key={range}
                  styles={{
                    root: {
                      display: 'inline-flex',
                      alignItems: 'center',
                      cursor: 'pointer',
                    },
                    inner: { display: 'none' },
                    label: {
                      backgroundColor: verseRange === range ? '#d3d3d3' : '#f5f5f5',
                      padding: '8px 12px',
                      borderRadius: '4px',
                      border: `1px solid ${verseRange === range ? '#888' : '#ccc'}`,
                      cursor: 'pointer',
                      transition: 'background-color 0.2s ease, border-color 0.2s ease',
                      display: 'inline-block',
                      whiteSpace: 'nowrap',
                    },
                  }}
                />
              ))}
            </Radio.Group>
          </div>
        </>
      )}

      {chapter && verseRange && (
        <Box mt="md">
          <Text size="lg" fw="bold">
            {book} {chapter}:{verseRange}
          </Text>
          <pre style={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
            {displayVerses(verseRange)}
          </pre>
        </Box>
      )}
    </div>
  );
}
