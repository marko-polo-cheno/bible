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

- `frontend/` — Vite + React + Mantine app (olive/almond design system in `src/theme.ts`
  and `src/global.css`)
- `backend/` — FastAPI service on Railway (Bible AI search, eLibrary pipeline)

## Contributing

Suggestions welcome — LMK or open a pull request.
