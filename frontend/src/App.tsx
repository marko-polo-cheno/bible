import { MantineProvider } from '@mantine/core';
import { Tabs } from '@mantine/core';
import { BibleNavigator } from './BibleNavigator/BibleNavigator';
import { SimilarBibleVerses } from './SimilarBibleVerses/SimilarBibleVerses';
import BibleSearch from './BibleSearch/BibleSearch';
import '@mantine/core/styles.layer.css';
function App() {
  return (
    <MantineProvider withGlobalStyles withNormalizeCSS>
      <div>
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
            <BibleSearch />
          </Tabs.Panel>
        </Tabs>
      </div>
    </MantineProvider>
  );
}

export default App;
