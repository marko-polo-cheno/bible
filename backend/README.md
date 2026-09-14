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
  `classification/*.labels.jsonl` + `sermon_taxonomy_full_paths.txt`), plus
  `fileTypes` — the flat catalog facet (see below).
- `GET  /elibrary/status` — join-map + semantic-index readiness.
- `POST /elibrary/search` — body `{stages: [...], langIds?, fileTypes?, page, size}`.
  Stage types: `filter` `{tree, prefixes}`, `keyword` `{terms, includeDerivatives}`,
  `semantic` `{query, topK}`. Returns per-stage funnel counts + ranked items.

`langIds` and `fileTypes` are **top-level scope**, not stages: they intersect
the candidate pool before the first stage runs, so funnel counts are already
relative to what the user asked for. An empty/absent list means "everything".

Modules: `elibrary.py` (join map + trees), `catalog.py` (file-type facet),
`corpus_index.py` (byte offsets into the corpora), `pipeline.py` (orchestrator),
`rag_search.py` (in-process FAISS + BGE-M3).

### File type — the third metadata axis

Neither category tree says *what kind of thing* an item is, so a third,
non-topical facet comes from the CMS catalog exports — the **medium**:

| medium | items | granular types beneath it |
| --- | --- | --- |
| `/Audio` | 485 | Sermon, Testimony, Lecture, Convocation, Evangelical Service, Prayer, Sacrament |
| `/Video` | 2,523 | Sermon, Outreach, Lecture, Evangelical Service, Prayer, Convocation, Testimony, Sacrament, Other |
| `/Document` | 10,969 | Articles, Book chapters, Lecture notes |
| `/Other` | 10,576 | — |

Every audio container (mp3, m4a, wav, …) is one **Audio**; every text format
(htm, html, pdf, doc, …) is one **Document**. Beneath the medium sits the type
the CMS already records — `ContentType` for media, `ItemSubType` for documents.
It is a `{name, value, children}` tree with `/`-paths, so `fileTypes:
["/Audio"]` takes every occasion under it and `["/Audio/Sermon"]` just the one,
prefix-matched by the same `matches_prefixes` the category trees use. Mixed
depths in one request are fine. `/elibrary/trees` prunes branches with no items.

**Format** — how you can consume the item — is a separate, orthogonal scope
(`formats: ["pdf"]`), because a Document can be both a web page and a PDF and an
mp3 exists under two mediums. `pdf`, `html`, `mp3` and `video` are extracted per
item; multi-select is a union, and it intersects with the file-type tree, so
`/Document` + `pdf` is documents that have a PDF. A streaming host is not a
format and is not a facet — it rides along as `videoHost` (`youtube` 2,522,
`vimeo` 1) for badging and deep links.

`/elibrary/trees` only offers a format that tells you something the medium does
not — under 10 items, or inside one medium and covering ≥95% of it, and it is
pruned. Today that serves **PDF** (2,768, a quarter of `/Document`) and **MP3
audio** (2,659, spanning `/Audio` 485 + `/Video` 2,174, which also splits
`/Video` into 2,174 downloadable and 349 stream-only). `html` is dropped as a
restatement of `/Document` (10,966 of 10,969). `catalog/formats.json` is the
vocabulary, not the served list — expect entries there that are pruned away.

Note `PdfURL` holds the literal string `"NULL"` when absent, so an emptiness
test wrongly reports that every publication has a PDF; only ~14% do.

Built offline by `_catalog/build_catalog.py` into `catalog/{en,zh}.catalog.jsonl`
(8 MB) — the API never opens a 68 MB CSV and never sniffs an encoding at request
time. `catalog/file_types.json` is the single source of truth for the facet list
and is served verbatim to the UI; `/elibrary/trees` drops any facet with zero
items rather than rendering a dead chip.

**`Other` is a stale export, not a category.** All 10,576 are uncatalogued, and
10,570 of them have an `ItemID` above 55064 — the highest the May 2025 exports
reach, while the corpus runs to 66090. They are articles published after the
snapshot. A fresh CMS export should move ~95% of them into `Document`. Until
then `Other` stays selectable so filtering never silently hides them.

### TableOfContents items are dropped at the source

`build_join_map` reads the catalog first and skips those keys while reading the
corpus, so TOC items are never constructed. They cannot be keyword-matched,
ranked, embedded-searched or returned, and they do not sit in `candidate_keys()`
— no pipeline stage and no frontend guard needed. 319 of the 1,340 catalogued
TOC rows exist in the corpus today.

### Keyword stage reads only the lines it needs

`corpus_index.py` keeps a byte-offset index (`item_id -> offset`) per corpus
file, cached beside it as `*.jsonl.offsets.npz` and rebuilt only when the corpus
changes. The keyword stage seeks to the pool's lines instead of streaming all
314 MB and `json.loads`-ing ~315k records. Anything an earlier stage dropped —
a category filter, a language, a file type, and every TOC item — is never read
or parsed. Measured on the 217 MB ZH corpus: a full-pool keyword search is
roughly unchanged (0.66s vs 0.53s — seeks cost a little when you want every
line), while a scoped one is 3–5× faster (0.13–0.19s). Offsets are visited in
ascending order so reads stay sequential, and the index is prewarmed at startup
alongside the join map.

### Semantic stage — deployment (single service)

Semantic search runs **in-process** (one Railway service). Artifacts live on
disk permanently; the weights live in RAM only while people are using the site.

Requirements:

1. Run `poetry lock` after the `faiss-cpu` / `FlagEmbedding` / `torch` (CPU)
   additions to `pyproject.toml`.
2. Service plan **≥ 6 GB RAM**. Measured steady state is 3.9 GB once the first
   query has touched every model weight (2.7 GB after load — FAISS and the row
   map, plus mmap'd BGE-M3 — rising to 3.9 GB on the first forward pass). The
   join map itself costs only ~0.03 GB since it holds no content.
3. Index artifacts (~1.7 GB: 1.29 GB `faiss.index` + 431 MB `metadata.jsonl`)
   are fetched from GitHub on first boot when not present locally (same repo as
   testimonies). Override with `RAG_FAISS_URL`, `RAG_METADATA_URL`, or
   `RAG_INDEX_DIR` if needed.

If artifact fetch or model load fails, keyword + filter search still work;
semantic reports `warming up` and passes the pool through unchanged.

#### Memory lifecycle (why idle RAM is ~0.1 GB, not 3.9 GB)

Boot did the loading, so idle cost used to equal active cost. Now the two are
separated — `rag_search.start()` runs at startup and:

1. **Fetches the artifacts to disk** (`ensure_artifacts`) and builds a
   `rowmap.npz` sidecar beside `metadata.jsonl`, so no user ever waits on a
   download or a 431 MB JSON parse. Chunk *text* is no longer held in RAM at
   all: snippets are seeked out of `metadata.jsonl` for the handful of rows a
   query returns.
2. **Warms eagerly** (FAISS + BGE-M3), so a fresh deploy is already hot.
3. **Starts an idle reaper** that unloads the stack after `RAG_IDLE_TTL`
   seconds with no eLibrary traffic, `malloc_trim`s the arenas back to the OS,
   and leaves the artifacts on disk.

Re-warming is hidden behind the funnel rather than charged to the query.
Requests under `/elibrary` (except `/elibrary/status`) mark activity and kick
off a load if the stack was evicted — the page mount hits `/elibrary/trees`
long before the user has picked filters and typed, so the load overlaps with
their typing. A semantic query that still arrives cold **waits** for the load
(up to `RAG_WARM_TIMEOUT`) instead of degrading. The health check, the Bible
reader and `/elibrary/status` deliberately do *not* count as activity, or the
reaper would never fire.

Knobs (all optional):

| Env | Default | Meaning |
| --- | --- | --- |
| `RAG_EAGER_WARM` | `1` | Load at startup. `0` = load on first eLibrary request. |
| `RAG_IDLE_TTL` | `1800` | Seconds of quiet before eviction. `0` disables eviction (idle RAM stays at 3.9 GB). |
| `RAG_IDLE_CHECK` | `60` | Reaper poll interval. |
| `RAG_WARM_TIMEOUT` | `240` | How long a cold semantic query waits for the load. |

`GET /elibrary/status` reports the lifecycle: `ready` (semantic will answer),
`resident` (in RAM right now), `loading`, `idleSeconds`, `loads`, `evictions`.
`POST /elibrary/search` carries the same split as `semanticReady` /
`semanticResident` — after an eviction `ready` stays true while `resident` is
false, so read `resident` if you care about latency rather than availability.

Two knock-on effects worth knowing: anything that *polls* an `/elibrary` route
other than `/status` will pin the stack warm (nothing does today), and a
semantic query that arrives with no preceding `/elibrary/trees` starts the warm
itself and waits for it — correct, just slower than the trees-first path.

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
