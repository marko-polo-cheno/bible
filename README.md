# Almonds & Olives

A small orchard of tools for studying the Bible — live at [almondsandolives.ca](https://almondsandolives.ca).

## Live apps

- **Bible** — a reader-first Bible app (NKJV · NASB · 中文 · Pīnyīn). Tap any verse to expand
  its *Connected Verses* (semantic nearest neighbours), search by meaning via the AI search
  overlay, and hop books/chapters with a YouVersion-style picker. Works great on phones and
  laptops.
- **eLibrary** — staged-pipeline search (keyword + category filters + semantic RAG) across
  24,000+ sermons, publications and testimonies.

## Coming soon (vision docs)

One README per idea, covering vision, plan and strategy:

- [Live Translator](docs/ideas/live-translator.md) — real-time sermon translation with verse-lock
- [The Journey](docs/ideas/the-journey.md) — chronological Bible pilgrimage on a living map
- [Sabbath Notes](docs/ideas/sabbath-notes.md) — the congregation fills one Bible with sticky notes
- [Memory Garden](docs/ideas/memory-garden.md) — spaced-repetition memorization as a growing orchard
- [Hymn Companion](docs/ideas/hymn-companion.md) — hymns linked to the scriptures they sing

## Repo layout

Two live apps share one SPA and one API. Offline packages produce the indexes
and labels the API serves at runtime.

```
frontend  ──static Bible JSON──►  reader (Connected Verses, book picker)
    │
    └──HTTP──►  backend (Railway)
                  ├── /search            OpenAI passage lookup
                  └── /elibrary/*        staged pipeline
                        ├── scope        lang + file type from _catalog
                        ├── filter       labels from _gemini_classifier
                        ├── keyword      testimonies_{en,zh}.jsonl (seeked)
                        └── semantic     FAISS + BGE-M3 from _rag
```

### Live product

- `frontend/` — Vite + React + Mantine SPA (olive/almond design in `src/theme.ts`
  and `src/global.css`). Hash routes: `/` home, `/bible` reader, `/elibrary`
  search. Bible text and the nearest-neighbour map load as static JSON
  (`data/{NKJV,NASB,chinese,pinyin,nn}.json`); tapping a verse expands
  *Connected Verses* locally. Meaning search and eLibrary queries hit the API
  (`VITE_API_URL`, else localhost in dev / Railway in prod). Published to
  GitHub Pages via `./deploy.sh`.
- `backend/` — FastAPI on Railway (`app.py`). Bible AI search
  (`bible_search.py`) returns structured passages. eLibrary is a staged
  funnel (`pipeline.py`): **filter** (legacy publication tree + LLM topical
  tree) → **keyword** → **semantic**. `elibrary.py` holds a metadata-only
  join map over `testimonies_{en,zh}.jsonl` (~24k items) plus
  `classification/*.labels.jsonl`. `rag_search.py` keeps the FAISS index and
  BGE-M3 in-process: artifacts stay on disk, the stack is warmed at boot and
  evicted after a quiet period, then re-warmed on the next eLibrary page load
  so idle RAM is ~0.1 GB instead of 3.9 GB (see `backend/README.md`).

### Offline pipelines (feed the API)

- `_rag/` — chunks and embeds the testimony corpora with BGE-M3, writes
  `_rag/index/{faiss.index,metadata.jsonl}`. Production does **not** run this
  service; the backend fetches those artifacts (or reads them locally) and
  serves queries itself.
- `_catalog/` — converts the four CMS catalog exports (68 MB, mixed encodings)
  into `backend/catalog/*.catalog.jsonl`: the grouped **medium** facet
  (Audio / Video / Document / Other, each split by the CMS type beneath it) and
  the format axis (PDF / web page), keyed by `(lang_id, item_id)`, plus
  the `TableOfContents` flags the API uses to drop those items before they are
  ever searchable.
- `_gemini_classifier/` — Gemini multi-label classification of every
  eLibrary item into the 274-node sermon taxonomy
  (`sermon_taxonomy_full_paths.txt` + `sermon_taxonomy_definitions.md`).
  Writes `backend/classification/{en,zh}.gemini37f.labels.jsonl`, which the
  join map reads at startup.

### Experiments

- `_speaker_isolation/` — two-speaker isolation recorder (groundwork for
  [Live Translator](docs/ideas/live-translator.md)).
- `docs/ideas/` — vision / plan / strategy notes for apps not built yet.

## Contributing

Suggestions welcome — LMK or open a pull request.
