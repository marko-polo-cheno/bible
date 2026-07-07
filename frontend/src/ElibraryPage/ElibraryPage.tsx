import { Link } from 'react-router-dom';
import { Anchor } from '@mantine/core';
import ElibrarySearch from '../ElibrarySearch/ElibrarySearch';

function ElibraryPage() {
  return (
    <div>
      <Anchor component={Link} to="/" px="md" pt="xs" style={{ display: 'inline-block' }}>
        ← Home
      </Anchor>
      <ElibrarySearch />
    </div>
  );
}

export default ElibraryPage;
