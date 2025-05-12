import { useState } from 'react';

export default function AIBibleSearch() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleSearch = async () => {
    setLoading(true);
    const res = await fetch(
      `https://bible-drab.vercel.app/api/search?query=${encodeURIComponent(query)}`
    );
    const data = await res.json();
    setResult(data);
    setLoading(false);
  };

  return (
    <div>
      <h2>AI Bible Search</h2>
      <input
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="What are you looking for from the Bible?"
      />
      <button onClick={handleSearch} disabled={loading}>
        Search
      </button>
      {loading && <p>Loading...</p>}
      {result && (
        <div>
          <h3>Passages</h3>
          <pre>{JSON.stringify(result.passages, null, 2)}</pre>
          <h3>Secondary Passages</h3>
          <pre>{JSON.stringify(result.secondary_passages, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}