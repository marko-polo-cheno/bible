# Bible Search API

AI-powered Bible search API using FastAPI and OpenAI.

## Setup

### Prerequisites
- Python 3.8+
- Poetry (install from https://python-poetry.org/docs/#installation)

### Installation

1. Install dependencies:
```bash
poetry install
```

2. Activate the virtual environment:
```bash
poetry shell
```

3. Set your OpenAI API key:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

### Running the API

Start the development server:
```bash
poetry run start
```

Or manually:
```bash
poetry run uvicorn search:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### API Endpoints

- `GET /` - Health check
- `GET /search?query=<search_term>&result_count=<one|few|many>&content_type=<verses|passages|all>&model_type=<fast|advanced>` - Search for Bible passages

## eLibrary search (unified, staged pipeline)

A single search engine over all eLibrary items (`testimonies_{en,zh}.jsonl`,
24k+ items) combining keyword, category-filter, and semantic (RAG) search as a
**staged pipeline** — each stage narrows the previous stage's candidate pool.

- `GET  /elibrary/trees` — both filter trees: `legacy` (publication-format,
  from `categories.py`) and `taxonomy` (LLM topical, from
  `classification/*.labels.jsonl` + `sermon_taxonomy_full_paths.txt`).
- `GET  /elibrary/status` — join-map + semantic-index readiness.
- `POST /elibrary/search` — body `{stages: [...], langIds?, page, size}`. Stage
  types: `filter` `{tree, prefixes}`, `keyword` `{terms, includeDerivatives}`,
  `semantic` `{query, topK}`. Returns per-stage funnel counts + ranked items.

Modules: `elibrary.py` (join map + trees), `pipeline.py` (orchestrator),
`rag_search.py` (in-process FAISS + BGE-M3).

### Semantic stage — deployment (single service)

Semantic search runs **in-process** (one Railway service). It loads the
prebuilt FAISS index + BGE-M3 model once in a background thread at startup;
keyword/filter work immediately and the semantic stage turns on when ready.

Requirements:

1. Run `poetry lock` after the `faiss-cpu` / `FlagEmbedding` / `torch` (CPU)
   additions to `pyproject.toml`.
2. Service plan **≥ 4 GB RAM** (≈2.3 GB model + 0.3 GB FAISS + metadata).
3. The index artifacts are too large to ship in the image — build them offline
   (CPU, see `_rag/README.md`) and host them, then set at runtime:
   - `RAG_FAISS_URL`, `RAG_METADATA_URL` — download URLs, or
   - `RAG_INDEX_DIR` — a mounted directory containing `faiss.index` +
     `metadata.jsonl`.

Without these, keyword + filter search work fully; semantic reports
`warming up` and passes the pool through unchanged.

### Development

Run tests:
```bash
poetry run pytest
```

Format code:
```bash
poetry run black .
poetry run isort .
```

Lint code:
```bash
poetry run flake8 .
```

## Migration from Conda

This project has been migrated from conda to Poetry for better dependency management and reproducibility.
