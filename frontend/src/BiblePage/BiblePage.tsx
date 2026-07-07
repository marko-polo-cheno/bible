import { Link } from 'react-router-dom';
import { Anchor, Tabs } from '@mantine/core';
import { BibleNavigator } from '../BibleNavigator/BibleNavigator';
import { SimilarBibleVerses } from '../SimilarBibleVerses/SimilarBibleVerses';
import BibleSearch from '../BibleSearch/BibleSearch';
import { BibleChatProvider } from '../contexts/BibleChatContext';

function BiblePage() {
  return (
    <div>
      <Anchor component={Link} to="/" px="md" pt="xs" style={{ display: 'inline-block' }}>
        ← Home
      </Anchor>
      <Tabs defaultValue="bibleSearch">
        <Tabs.List>
          <Tabs.Tab value="bibleNavigator">Bible Navigator</Tabs.Tab>
          <Tabs.Tab value="similarBibleVerses">Connected Verses</Tabs.Tab>
          <Tabs.Tab value="bibleSearch">Bible Search</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="bibleNavigator" pt="xs">
          <BibleNavigator />
        </Tabs.Panel>
        <Tabs.Panel value="similarBibleVerses" pt="xs">
          <SimilarBibleVerses />
        </Tabs.Panel>
        <Tabs.Panel value="bibleSearch" pt="xs">
          <BibleChatProvider>
            <BibleSearch />
          </BibleChatProvider>
        </Tabs.Panel>
      </Tabs>
    </div>
  );
}

export default BiblePage;
