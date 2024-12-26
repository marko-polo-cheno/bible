import { MantineProvider } from '@mantine/core';
import { Tabs } from '@mantine/core';
import { BibleNavigator } from './components/BibleNavigator';

function App() {
  return (
    <MantineProvider withGlobalStyles withNormalizeCSS>
      <div>
        <Tabs defaultValue="bibleNavigator">
          <Tabs.List>
            <Tabs.Tab value="bibleNavigator">Bible Navigator</Tabs.Tab>
            <Tabs.Tab value="placeholder">Other App</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="bibleNavigator" pt="xs">
            <BibleNavigator />
          </Tabs.Panel>
          <Tabs.Panel value="placeholder" pt="xs">
            Placeholder for other apps.
          </Tabs.Panel>
        </Tabs>
      </div>
    </MantineProvider>
  );
}

export default App;
