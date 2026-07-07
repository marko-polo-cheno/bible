import { Link } from 'react-router-dom';
import BranchLogo from '../components/BranchLogo';
import ElibrarySearch from '../ElibrarySearch/ElibrarySearch';

function ElibraryPage() {
  return (
    <div>
      <header className="ao-appbar">
        <Link to="/" className="ao-appbar-logo" aria-label="Home">
          <BranchLogo />
        </Link>
        <span className="ao-appbar-title">eLibrary</span>
      </header>
      <ElibrarySearch />
    </div>
  );
}

export default ElibraryPage;
