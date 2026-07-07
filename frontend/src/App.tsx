import { MantineProvider } from '@mantine/core';
import { HashRouter, Route, Routes } from 'react-router-dom';
import HomePage from './HomePage/HomePage';
import BiblePage from './BiblePage/BiblePage';
import ElibraryPage from './ElibraryPage/ElibraryPage';
import '@mantine/core/styles.layer.css';

function App() {
  return (
    <MantineProvider withGlobalStyles withNormalizeCSS>
      <HashRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/bible" element={<BiblePage />} />
          <Route path="/elibrary" element={<ElibraryPage />} />
        </Routes>
      </HashRouter>
    </MantineProvider>
  );
}

export default App;
